package com.example.stockkkkk.news.repository;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Transactional
@Disabled
class RepositoryTest {

    @Autowired
    private ArticleRegistryRepository articleRepository;

    @Test
    void 레포지토리_주입_확인() {
        assertThat(articleRepository).isNotNull();
        System.out.println("레포지토리 정상 주입됨");
    }
}
