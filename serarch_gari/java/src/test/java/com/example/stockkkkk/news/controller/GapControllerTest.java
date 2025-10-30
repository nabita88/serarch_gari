package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.dto.GapStats;
import com.example.stockkkkk.news.service.GapService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(GapController.class)
class GapControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private GapService gapService;

    @Test
    void checkGaps() throws Exception {
        when(gapService.checkGaps(anyString(), anyInt()))
            .thenReturn(List.of());
        when(gapService.calculatePriceChange(anyString(), anyInt()))
            .thenReturn(0.0);

        mockMvc.perform(get("/api/gaps/check/005930"))
            .andExpect(status().isOk());
    }

    @Test
    void listGaps() throws Exception {
        when(gapService.findGapsWithFilters(anyInt(), anyString(), anyString(), anyDouble(), anyInt()))
            .thenReturn(List.of());

        mockMvc.perform(get("/api/gaps/list"))
            .andExpect(status().isOk());
    }

    @Test
    void getStats() throws Exception {
        when(gapService.calculateStats(anyInt()))
            .thenReturn(new GapStats(0L, 0L, 0L, 0.0));

        mockMvc.perform(get("/api/gaps/stats"))
            .andExpect(status().isOk());
    }
}
