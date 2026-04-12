package com.rithin.AutoDocx.controller;

import org.springframework.web.bind.annotation.*;
import com.rithin.AutoDocx.service.HelloService;

@RestController
public class TestController {

    private final HelloService helloService;

    // Constructor Injection (IMPORTANT)
    public TestController(HelloService helloService) {
        this.helloService = helloService;
    }

    @GetMapping("/")
    public String hello() {
        return helloService.getMessage();
    }

    @DeleteMapping("/remove")
    public String remove() {
        System.out.println("Remove request received");
        return "Removed";
    }