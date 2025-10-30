package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.dto.*;
import com.example.stockkkkk.news.service.GapService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/gaps")
@RequiredArgsConstructor
public class GapController {

    private final GapService gapService;

    @GetMapping("/check/{stockCode}")
    public ResponseEntity<GapCheckResponse> checkGaps(
        @PathVariable String stockCode,
        @RequestParam(defaultValue = "100") int days
    ) {
        GapCheckResponse response = gapService.checkGaps(stockCode, days);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/list")
    public ResponseEntity<GapListResponse> listGaps(
        @RequestParam(defaultValue = "100") int days,
        @RequestParam(required = false) String direction,
        @RequestParam(required = false) String magnitude,
        @RequestParam(defaultValue = "2.0") double minZ,
        @RequestParam(defaultValue = "100") int limit
    ) {
        List<GapHistoryDto> gaps = gapService.findGapsWithFilters(days, direction, magnitude, minZ, limit);
        return ResponseEntity.ok(new GapListResponse(gaps));
    }

    @GetMapping("/stats")
    public ResponseEntity<GapStatisticsDto> getStats(
        @RequestParam(defaultValue = "100") int days
    ) {
        GapStatisticsDto stats = gapService.calculateDetailedStats(days);
        log.info("Returning stats: total={}, byDirection={}", stats.getTotal(), stats.getByDirection());
        return ResponseEntity.ok(stats);
    }

    @GetMapping("/stats/simple")
    public ResponseEntity<GapStats> getSimpleStats(
        @RequestParam(defaultValue = "7") int days
    ) {
        GapStats stats = gapService.calculateStats(days);
        return ResponseEntity.ok(stats);
    }
}
