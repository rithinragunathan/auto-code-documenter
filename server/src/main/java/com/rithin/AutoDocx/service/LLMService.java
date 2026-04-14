package com.rithin.AutoDocx.service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@Service
public class LLMService {

    private static final Logger logger = LoggerFactory.getLogger(LLMService.class);

    @Value("${python.service.url}")
    private String pythonServiceUrl;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .build();

    private final ObjectMapper objectMapper = new ObjectMapper();

    public String analyzeCode(String code, String language, String prompt, String requestType) {
        try {
            logger.info("Sending code to Python service for analysis");
            
            // Build request to Python service
            String pythonResponse = callPythonService(code, language, prompt, requestType);
            
            logger.info("Received analysis from Python service");
            return pythonResponse;
        } catch (Exception e) {
            logger.error("Error calling Python service: {}", e.getMessage(), e);
            return getErrorResponse(code, language, requestType, e.getMessage());
        }
    }

    private String callPythonService(String code, String language, String prompt, String requestType) throws Exception {
        // Build request body
        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("code", code);
        requestBody.put("language", language);
        requestBody.put("request_type", requestType);
        if (prompt != null && !prompt.isEmpty()) {
            requestBody.put("prompt", prompt);
        }

        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        // Build HTTP request to Python service
        HttpRequest request = HttpRequest.newBuilder()
                .uri(new URI(pythonServiceUrl + "/api/analyze"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBodyString))
                .build();

        // Send request with timeout
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            logger.error("Python service error: {} - {}", response.statusCode(), response.body());
            throw new RuntimeException("Python service returned status: " + response.statusCode());
        }

        // Parse response
        ObjectNode responseBody = objectMapper.readValue(response.body(), ObjectNode.class);
        
        // Extract analysis from response
        String analysis = responseBody
                .get("analysis")
                .asText();

        return analysis;
    }

    private String getErrorResponse(String code, String language, String requestType, String errorMessage) {
        StringBuilder response = new StringBuilder();
        response.append("**Error in Analysis**\n\n");
        response.append("Request Type: ").append(requestType).append("\n");
        response.append("Language: ").append(language).append("\n");
        response.append("Error: ").append(errorMessage).append("\n\n");
        response.append("**Troubleshooting:**\n");
        response.append("1. Ensure Python service is running on ").append(pythonServiceUrl).append("\n");
        response.append("2. Check if GOOGLE_API_KEY is set in the Python service .env file\n");
        response.append("3. Verify network connectivity between Spring Boot and Python service\n");
        response.append("4. Check Python service logs for detailed error messages\n");
        return response.toString();
    }
}
