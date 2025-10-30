package com.example.stockkkkk.global.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.orm.jpa.EntityManagerFactoryBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.orm.jpa.JpaTransactionManager;
import org.springframework.orm.jpa.LocalContainerEntityManagerFactoryBean;
import org.springframework.transaction.PlatformTransactionManager;

import javax.sql.DataSource;
import java.util.HashMap;
import java.util.Map;

@Configuration
@EnableJpaRepositories(
    basePackages = {
        "com.example.stockkkkk.news.repository",
        "com.example.stockkkkk.auser.repository",
        "com.example.stockkkkk.disclosure.repository"
    },
    entityManagerFactoryRef = "newsEntityManagerFactory",
    transactionManagerRef = "newsTransactionManager"
)
public class DatabaseConfig {

    @Value("${spring.datasource.url}")
    private String url;

    @Value("${spring.datasource.username}")
    private String username;

    @Value("${spring.datasource.password}")
    private String password;

    @Bean(name = "newsDataSource")
    @Primary
    public DataSource newsDataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(url);
        config.setUsername(username);
        config.setPassword(password);
        config.setDriverClassName("org.mariadb.jdbc.Driver");
        return new HikariDataSource(config);
    }

    @Bean(name = "newsEntityManagerFactory")
    @Primary
    public LocalContainerEntityManagerFactoryBean newsEntityManagerFactory(
        EntityManagerFactoryBuilder builder,
        @Qualifier("newsDataSource") DataSource dataSource) {
        
        Map<String, Object> properties = new HashMap<>();
        properties.put("hibernate.dialect", "org.hibernate.dialect.MariaDBDialect");
        properties.put("hibernate.hbm2ddl.auto", "none");
        
        return builder
            .dataSource(dataSource)
            .packages(
                "com.example.stockkkkk.news.domain",
                "com.example.stockkkkk.auser.domain",
                "com.example.stockkkkk.disclosure.domain"
            )
            .persistenceUnit("news")
            .properties(properties)
            .build();
    }

    @Bean(name = "newsTransactionManager")
    @Primary
    public PlatformTransactionManager newsTransactionManager(
        @Qualifier("newsEntityManagerFactory") LocalContainerEntityManagerFactoryBean factory) {
        return new JpaTransactionManager(factory.getObject());
    }
}
