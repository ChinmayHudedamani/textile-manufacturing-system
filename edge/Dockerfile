FROM alpine:3.19 AS builder
RUN apk add --no-cache g++ cmake make git paho-mqtt-cpp-dev nlohmann-json
WORKDIR /app
COPY edge_telemetry.cpp CMakeLists.txt ./
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build

FROM alpine:3.19
RUN apk add --no-cache libstdc++ paho-mqtt-c
WORKDIR /root/
COPY --from=builder /app/build/edge_telemetry .
ENTRYPOINT ["./edge_telemetry"]
