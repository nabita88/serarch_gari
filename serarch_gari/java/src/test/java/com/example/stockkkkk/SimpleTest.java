package com.example.stockkkkk;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SimpleTest {

    @Test
    void 기본_테스트() {
        assertThat(1 + 1).isEqualTo(2);
        System.out.println("테스트 성공");
    }
}
