#!/bin/sh

# PEAR RabbitMQ Init Script - Creates admin user then starts RabbitMQ
echo "=== PEAR RabbitMQ Initialization ==="

# For Kubernetes clustering, preserve the nodename from environment
# Don't override RABBITMQ_NODENAME if it's already set for clustering
if [ -z "$RABBITMQ_NODENAME" ]; then
    echo "Setting nodename for standalone mode"
    echo 'NODENAME=rabbit@localhost' > /etc/rabbitmq/rabbitmq-env.conf
else
    echo "Using Kubernetes nodename: $RABBITMQ_NODENAME"
fi

# Determine which vhost to use
if [ -n "$RABBITMQ_DEFAULT_VHOST" ] && [ "$RABBITMQ_DEFAULT_VHOST" != "vhost" ]; then
    VHOST_TO_USE="$RABBITMQ_DEFAULT_VHOST"
    echo "Will create custom vhost: $VHOST_TO_USE"
else
    VHOST_TO_USE="/"
    echo "Using default vhost: vhost"
fi

# Create admin user in background (this ensures user exists before definitions loading)
(rabbitmqctl wait --timeout 120 $RABBITMQ_PID_FILE ; \
echo "RabbitMQ is ready, creating admin user..." ; \
if [ "$VHOST_TO_USE" != "vhost" ]; then \
    echo "Creating vhost: $VHOST_TO_USE" ; \
    rabbitmqctl add_vhost "$VHOST_TO_USE" 2>/dev/null ; \
fi ; \
echo "Creating user: $RABBITMQ_USER" ; \
rabbitmqctl add_user "$RABBITMQ_USER" "$RABBITMQ_PASSWORD" 2>/dev/null ; \
echo "Setting user tags..." ; \
rabbitmqctl set_user_tags "$RABBITMQ_USER" administrator ; \
echo "Setting permissions on vhost: $VHOST_TO_USE" ; \
rabbitmqctl set_permissions -p "$VHOST_TO_USE" "$RABBITMQ_USER" ".*" ".*" ".*" ; \
echo "*** User '$RABBITMQ_USER' with password '$RABBITMQ_PASSWORD' completed. ***" ; \
echo "*** Vhost '$VHOST_TO_USE' ready with admin permissions ***" ; \
echo "*** PEAR RabbitMQ basic setup complete - ready for definitions loading ***") &

# Start RabbitMQ server
echo "Starting RabbitMQ server..."
rabbitmq-server $@
