# Glauria ERP Software Design Document

## 1. Introduction

### 1.1 Purpose

This document defines the technical design and software architecture of
Glauria ERP.

It explains how the functional and non-functional requirements defined
in the Software Requirements Specification will be implemented using
the selected technologies, architectural patterns and infrastructure
components.

The document serves as a technical reference for development, testing,
deployment and future maintenance activities.

### 1.2 Design Goals

The primary design goals of Glauria ERP are:

- Modularity
- Maintainability
- Data consistency
- Traceability
- Security
- Scalability
- Testability
- Clear separation of responsibilities
- Reliable background processing
- Controlled artificial intelligence integration

### 1.3 Architectural Style

Glauria ERP shall be developed using a modular monolithic architecture.

The system will operate as a single Django project while business
domains are separated into independent Django applications.

This architecture provides centralized transaction management and data
consistency while allowing each business domain to maintain its own
models, services, views, templates and tests.
## 2. System Architecture

The system consists of the following main components:

- Web browser client
- NGINX reverse proxy
- Gunicorn WSGI application server
- Django application
- PostgreSQL relational database
- Redis cache and message broker
- Celery worker
- Celery Beat scheduler
- OpenAI API and AI integration services
- Sentry, Prometheus and Grafana monitoring services

The primary request flow is:

```text
Web Browser
    ↓
NGINX
    ↓
Gunicorn
    ↓
Django Application
    ↓
Service Layer
    ↓
Django ORM
    ↓
PostgreSQL