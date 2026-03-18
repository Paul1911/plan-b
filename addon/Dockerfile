ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python, git, and uv
RUN apk add --no-cache python3 py3-pip curl git \
    && curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Clone repo and install dependencies
WORKDIR /app
RUN git clone --depth 1 https://github.com/Paul1911/plan-b.git . \
    && uv pip install --system --no-cache -r requirements.txt

# Copy add-on run script
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
