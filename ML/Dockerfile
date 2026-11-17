# Используем легковесный образ Python 3.11 (совместим с большинством pickled scikit-learn моделей)
FROM python:3.11-slim

# Отключаем буферизацию вывода (логи сразу видны в docker logs) и генерацию .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libgomp1 нужен для OpenMP в numpy/scipy/sklearn
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости отдельным слоем для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаём непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 mluser

# Копируем исходный код и веса модели
COPY --chown=mluser:mluser . .

USER mluser

CMD ["python", "-m", "app"]