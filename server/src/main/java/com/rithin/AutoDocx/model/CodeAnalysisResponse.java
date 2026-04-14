package com.rithin.AutoDocx.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class CodeAnalysisResponse {

    @JsonProperty("id")
    private String id;

    @JsonProperty("original_code")
    private String originalCode;

    @JsonProperty("analysis_result")
    private String analysisResult;

    @JsonProperty("request_type")
    private String requestType;

    @JsonProperty("status")
    private String status;

    @JsonProperty("timestamp")
    private long timestamp;

    public CodeAnalysisResponse() {
    }

    public CodeAnalysisResponse(String id, String originalCode, String analysisResult, String requestType) {
        this.id = id;
        this.originalCode = originalCode;
        this.analysisResult = analysisResult;
        this.requestType = requestType;
        this.status = "SUCCESS";
        this.timestamp = System.currentTimeMillis();
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getOriginalCode() {
        return originalCode;
    }

    public void setOriginalCode(String originalCode) {
        this.originalCode = originalCode;
    }

    public String getAnalysisResult() {
        return analysisResult;
    }

    public void setAnalysisResult(String analysisResult) {
        this.analysisResult = analysisResult;
    }

    public String getRequestType() {
        return requestType;
    }

    public void setRequestType(String requestType) {
        this.requestType = requestType;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}
