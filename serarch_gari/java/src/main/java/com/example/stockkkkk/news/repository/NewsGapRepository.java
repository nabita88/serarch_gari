package com.example.stockkkkk.news.repository;

import com.example.stockkkkk.news.domain.NewsGap;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
@Repository
public interface NewsGapRepository extends JpaRepository<NewsGap, Long> {
    
    @Query("SELECT g FROM NewsGap g WHERE g.stockCode = :stockCode AND g.newsDate >= :afterDate")
    List<NewsGap> findByStockCodeAndNewsDateAfter(@Param("stockCode") String stockCode, @Param("afterDate") LocalDate date);
    
    @Query("SELECT g FROM NewsGap g WHERE g.newsDate >= :afterDate " +
           "AND (:direction IS NULL OR g.direction = :direction) " +
           "AND (:magnitude IS NULL OR g.magnitude = :magnitude) " +
           "AND ABS(g.zScore) >= :minZ " +
           "ORDER BY ABS(g.zScore) DESC")
    List<NewsGap> findGapsWithFilters(
        @Param("afterDate") LocalDate afterDate,
        @Param("direction") String direction,
        @Param("magnitude") String magnitude,
        @Param("minZ") Double minZ
    );
    
    @Query("SELECT COUNT(g) FROM NewsGap g WHERE g.newsDate >= :afterDate")
    long countByNewsDateAfter(@Param("afterDate") LocalDate afterDate);
    
    @Query("SELECT COUNT(g) FROM NewsGap g WHERE g.newsDate >= :afterDate AND g.direction = 'OVER'")
    long countOverByNewsDateAfter(@Param("afterDate") LocalDate afterDate);
    
    @Query("SELECT COUNT(g) FROM NewsGap g WHERE g.newsDate >= :afterDate AND g.direction = 'UNDER'")
    long countUnderByNewsDateAfter(@Param("afterDate") LocalDate afterDate);
    
    @Query("SELECT AVG(g.zScore) FROM NewsGap g WHERE g.newsDate >= :afterDate")
    Double avgZScoreByNewsDateAfter(@Param("afterDate") LocalDate afterDate);
}
