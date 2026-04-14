package com.rithin.AutoDocx.controller;

import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import com.rithin.AutoDocx.model.CodeAnalysisRequest;
import com.rithin.AutoDocx.model.CodeAnalysisResponse;
import com.rithin.AutoDocx.service.HelloService;
import com.rithin.AutoDocx.service.LLMService;

@RestController
@CrossOrigin(origins = "*", allowedHeaders = "*", methods = {RequestMethod.GET, RequestMethod.POST, RequestMethod.OPTIONS})
public class TestController {

    private final HelloService helloService;
    private final LLMService llmService;
    
    // Store analysis results in memory
    private final Map<String, CodeAnalysisResponse> analysisResults = new ConcurrentHashMap<>();

    // Constructor Injection (IMPORTANT)
    public TestController(HelloService helloService, LLMService llmService) {
        this.helloService = helloService;
        this.llmService = llmService;
    }

    @GetMapping("/")
    public String hello() {
        return helloService.getMessage();
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "UP");
        response.put("service", "AutoDocx Backend");
        response.put("timestamp", System.currentTimeMillis());
        return response;
    }

    @PostMapping("/api/analyze-code")
    public CodeAnalysisResponse analyzeCode(@RequestBody CodeAnalysisRequest request) {
        try {
            String id = UUID.randomUUID().toString();
            
            // Call LLM service
            String analysisResult = llmService.analyzeCode(
                    request.getCode(),
                    request.getLanguage(),
                    request.getPrompt(),
                    request.getRequestType()
            );
            
            // Create response
            CodeAnalysisResponse response = new CodeAnalysisResponse(
                    id,
                    request.getCode(),
                    analysisResult,
                    request.getRequestType()
            );
            
            // Store result for later retrieval
            analysisResults.put(id, response);
            
            return response;
        } catch (Exception e) {
            CodeAnalysisResponse errorResponse = new CodeAnalysisResponse();
            errorResponse.setId(UUID.randomUUID().toString());
            errorResponse.setStatus("ERROR");
            errorResponse.setAnalysisResult("Error: " + e.getMessage());
            return errorResponse;
        }
    }

    @GetMapping("/api/analysis/{id}")
    public ResponseEntity<CodeAnalysisResponse> getAnalysis(@PathVariable String id) {
        CodeAnalysisResponse result = analysisResults.get(id);
        if (result == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(result);
    }

    @GetMapping("/api/analysis-history")
    public Collection<CodeAnalysisResponse> getAnalysisHistory() {
        return analysisResults.values();
    }

    @DeleteMapping("/api/analysis/{id}")
    public Map<String, Object> deleteAnalysis(@PathVariable String id) {
        analysisResults.remove(id);
        Map<String, Object> response = new HashMap<>();
        response.put("message", "Analysis deleted");
        response.put("id", id);
        return response;
    }

    @DeleteMapping("/remove")
    public String remove() {
        System.out.println("Remove request received");
        return "Removed";
    }
}