FROM python:3.11-slim

WORKDIR /app

# 시스템 필수 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 패키지 빌드 파일 복사 및 의존성 설치
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 앱 코드 및 정적 데이터 복사
COPY configs ./configs
COPY data/assets ./data/assets
COPY app ./app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:/app

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]
