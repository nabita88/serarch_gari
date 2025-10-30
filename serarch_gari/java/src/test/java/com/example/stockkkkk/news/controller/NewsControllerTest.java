package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.domain.ArticleRegistry;
import com.example.stockkkkk.news.service.NewsService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Disabled("서비스가 주석처리되어 비활성화")
@WebMvcTest(NewsController.class)
class NewsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private NewsService newsService;

    @Test
    void getNewsByStock() throws Exception {
        when(newsService.findByStockCode(anyString(), anyInt(), anyInt()))
                .thenReturn(List.of());

        mockMvc.perform(get("/api/news/stock/005930"))
                .andExpect(status().isOk());
    }

    @Test
    void getNewsDetail() throws Exception {
        when(newsService.findByDocId(anyString()))
                .thenReturn(new ArticleRegistry());

        mockMvc.perform(get("/api/news/DOC123"))
                .andExpect(status().isOk());
    }

    @Test
    void getNewsByCategory() throws Exception {
        when(newsService.findByCategory(anyString(), anyInt()))
                .thenReturn(List.of());

        mockMvc.perform(get("/api/news/category/경제"))
                .andExpect(status().isOk());
    }

    @Test
    void getNewsByPublisher() throws Exception {
        when(newsService.findByPublisher(anyString(), anyInt()))
                .thenReturn(List.of());

        mockMvc.perform(get("/api/news/publisher/한국경제"))
                .andExpect(status().isOk());
    }
}
