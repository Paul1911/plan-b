ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and uv
RUN apk add --no-cache python3 curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY plan_b/ ./plan_b/

# Copy add-on run script
COPY addon/run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
