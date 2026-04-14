package com.rithin.AutoDocx.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class CodeAnalysisRequest {

    @JsonProperty("code")
    private String code;

    @JsonProperty("language")
    private String language;

    @JsonProperty("prompt")
    private String prompt;

    @JsonProperty("request_type")
    private String requestType; // e.g., "documentation", "review", "optimization", "bug_fix"

    public CodeAnalysisRequest() {
    }

    public CodeAnalysisRequest(String code, String language, String prompt, String requestType) {
        this.code = code;
        this.language = language;
        this.prompt = prompt;
        this.requestType = requestType;
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getLanguage() {
        return language;
    }

    public void setLanguage(String language) {
        this.language = language;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getRequestType() {
        return requestType;
    }

    public void setRequestType(String requestType) {
        this.requestType = requestType;
    }
}
