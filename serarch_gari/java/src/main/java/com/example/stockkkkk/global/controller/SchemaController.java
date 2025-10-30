package com.example.stockkkkk.global.controller;

import com.example.stockkkkk.global.util.DatabaseSchemaUtil;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/schema")
public class SchemaController {

    private final DatabaseSchemaUtil schemaUtil;

    public SchemaController(DatabaseSchemaUtil schemaUtil) {
        this.schemaUtil = schemaUtil;
    }

    @GetMapping("/tables")
    public List<String> getTables() {
        List<String> tables = schemaUtil.getAllTables();
        tables.forEach(schemaUtil::printTableStructure);
        return tables;
    }
}
