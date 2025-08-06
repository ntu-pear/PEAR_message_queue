FROM rabbitmq:4.1.1-management

# Set metadata
LABEL maintainer="PEAR Team"
LABEL description="RabbitMQ Message Broker for PEAR System"
LABEL version="1.0.0"

# Define environment variables for user creation
ENV RABBITMQ_USER admin
ENV RABBITMQ_PASSWORD pear2025
ENV RABBITMQ_PID_FILE /var/lib/rabbitmq/mnesia/rabbitmq

# Copy configuration files
COPY rabbitmq.conf /etc/rabbitmq/rabbitmq.conf
COPY definitions.yaml /etc/rabbitmq/definitions.json
COPY init.sh /init.sh

# Set proper permissions
RUN chmod 644 /etc/rabbitmq/rabbitmq.conf && \
    chmod 644 /etc/rabbitmq/definitions.json && \
    chmod +x /init.sh

# Expose ports
EXPOSE 5672 15672

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD rabbitmq-diagnostics ping

# Use our custom init script
CMD ["/init.sh"]
