package com.example.stockkkkk.global.util;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

@Component
public class DatabaseSchemaUtil {

    private final DataSource externalDataSource;

    public DatabaseSchemaUtil(@Qualifier("newsDataSource") DataSource externalDataSource) {
        this.externalDataSource = externalDataSource;
    }

    public List<String> getAllTables() {
        List<String> tables = new ArrayList<>();
        try (Connection conn = externalDataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SHOW TABLES")) {
            
            while (rs.next()) {
                tables.add(rs.getString(1));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return tables;
    }

    public void printTableStructure(String tableName) {
        try (Connection conn = externalDataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("DESCRIBE " + tableName)) {
            
            System.out.println("\n=== Table: " + tableName + " ===");
            while (rs.next()) {
                System.out.printf("%-30s %-20s %-10s %-10s\n",
                        rs.getString("Field"),
                        rs.getString("Type"),
                        rs.getString("Null"),
                        rs.getString("Key"));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
