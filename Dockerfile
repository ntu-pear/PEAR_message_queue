FROM rabbitmq:4.1.1-management

# Set metadata
LABEL maintainer="PEAR Team"
LABEL description="RabbitMQ Message Broker for PEAR System"
LABEL version="1.0.0"

# Set environment variables
ENV RABBITMQ_DEFAULT_USER=admin
ENV RABBITMQ_DEFAULT_PASS=pear2025
ENV RABBITMQ_DEFAULT_VHOST=/

# Copy configuration files
COPY rabbitmq.conf /etc/rabbitmq/rabbitmq.conf
COPY definitions.yaml /etc/rabbitmq/definitions.json

# Set proper permissions for config files
RUN chmod 644 /etc/rabbitmq/rabbitmq.conf && \
    chmod 644 /etc/rabbitmq/definitions.json

# Expose ports
EXPOSE 5672 15672

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD rabbitmq-diagnostics ping

CMD ["rabbitmq-server"]