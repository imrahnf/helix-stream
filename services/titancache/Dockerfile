# Stage 1: Build Stage (Uses full JDK to compile)
FROM maven:3.9.6-eclipse-temurin-21 AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
# Pre-fetch dependencies to speed up subsequent builds
RUN mvn dependency:go-offline -B
RUN mvn clean package -DskipTests

# Stage 2: Runtime Stage (Slim JRE for the distributed node)
FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

# JVM Tuning for 32GB RAM environments
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]