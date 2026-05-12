package com.sso.events;

import org.keycloak.events.Event;
import org.keycloak.events.EventListenerProvider;
import org.keycloak.events.admin.AdminEvent;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.HashMap;
import java.util.Map;

/**
 * Event Listener custom pour Keycloak.
 * À chaque événement (LOGIN, LOGIN_ERROR, LOGOUT...), on construit
 * un JSON et on l'envoie dans un topic Kafka.
 *
 * Le code est volontairement simple : pas de batch, pas de reconnect logic.
 * Pour un PFE c'est suffisant et lisible.
 */
public class KafkaEventListenerProvider implements EventListenerProvider {

    private final KafkaProducer<String, String> producer;
    private final String topic;
    private final ObjectMapper mapper = new ObjectMapper();

    public KafkaEventListenerProvider(KafkaProducer<String, String> producer, String topic) {
        this.producer = producer;
        this.topic = topic;
    }

    /**
     * Appelé à chaque événement utilisateur (login, logout, register...).
     */
    @Override
    public void onEvent(Event event) {
        try {
            Map<String, Object> data = new HashMap<>();
            data.put("time",       event.getTime());
            data.put("type",       event.getType().toString());
            data.put("realmId",    event.getRealmId());
            data.put("clientId",   event.getClientId());
            data.put("userId",     event.getUserId());
            data.put("ipAddress",  event.getIpAddress());
            data.put("error",      event.getError());
            data.put("sessionId",  event.getSessionId());
            data.put("details",    event.getDetails()); // contient username, user-agent...

            String json = mapper.writeValueAsString(data);
            producer.send(new ProducerRecord<>(topic, event.getIpAddress(), json));

        } catch (Exception e) {
            // On log mais on ne casse pas Keycloak en cas d'erreur Kafka
            System.err.println("[KafkaEventListener] Erreur envoi événement : " + e.getMessage());
        }
    }

    /**
     * Événements admin (création user, modif rôle...). On les envoie aussi.
     */
    @Override
    public void onEvent(AdminEvent adminEvent, boolean includeRepresentation) {
        try {
            Map<String, Object> data = new HashMap<>();
            data.put("time",         adminEvent.getTime());
            data.put("type",         "ADMIN_" + adminEvent.getOperationType().toString());
            data.put("realmId",      adminEvent.getRealmId());
            data.put("resourceType", adminEvent.getResourceTypeAsString());
            data.put("resourcePath", adminEvent.getResourcePath());

            String json = mapper.writeValueAsString(data);
            producer.send(new ProducerRecord<>(topic, "admin", json));

        } catch (Exception e) {
            System.err.println("[KafkaEventListener] Erreur événement admin : " + e.getMessage());
        }
    }

    @Override
    public void close() {
        // Le producer est partagé, on ne le ferme pas ici
    }
}
