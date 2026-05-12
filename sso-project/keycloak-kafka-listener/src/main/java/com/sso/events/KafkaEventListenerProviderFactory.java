package com.sso.events;

import org.keycloak.Config;
import org.keycloak.events.EventListenerProvider;
import org.keycloak.events.EventListenerProviderFactory;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;

/**
 * Factory : Keycloak instancie cette classe une fois au démarrage.
 * Elle crée le KafkaProducer (partagé) et fournit des Provider à la demande.
 */
public class KafkaEventListenerProviderFactory implements EventListenerProviderFactory {

    public static final String PROVIDER_ID = "kafka";

    private KafkaProducer<String, String> producer;
    private String topic;

    @Override
    public EventListenerProvider create(KeycloakSession session) {
        return new KafkaEventListenerProvider(producer, topic);
    }

    @Override
    public void init(Config.Scope config) {
        // Lecture des variables d'env définies dans docker-compose
        String bootstrap = System.getenv()
            .getOrDefault("KC_SPI_EVENTS_LISTENER_KAFKA_BOOTSTRAP_SERVERS", "kafka:9092");
        this.topic = System.getenv()
            .getOrDefault("KC_SPI_EVENTS_LISTENER_KAFKA_TOPIC", "keycloak-events");

        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrap);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.CLIENT_ID_CONFIG, "keycloak-event-listener");
        // Important : non bloquant pour ne pas ralentir Keycloak
        props.put(ProducerConfig.ACKS_CONFIG, "0");

        this.producer = new KafkaProducer<>(props);
        System.out.println("[KafkaEventListener] Producer initialisé -> " + bootstrap + " topic=" + topic);
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {}

    @Override
    public void close() {
        if (producer != null) producer.close();
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }
}
