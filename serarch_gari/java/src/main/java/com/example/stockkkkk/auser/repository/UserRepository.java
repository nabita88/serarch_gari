package com.example.stockkkkk.auser.repository;
import com.example.stockkkkk.auser.domain.Ausers;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<Ausers, Long> {

    Optional<Ausers> findByEmail(String email);

    boolean existsByEmail(String email);
}
