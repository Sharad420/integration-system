# integration-system
Built a fully async Python FastAPI backend with Redis session management, supporting OAuth integrations with Notion, Airtable, and HubSpot. Developed a Dockerized fullstack system with React frontend, supporting secure authentication flows and dynamic metadata aggregation.

To have it fully working
- Create your own Notion, Hubspot and AirTable apps and get the Client ID and Secrets from them.
- Put them in a .env page so that these codes are never exposed to the backend.
- Ensure port 6379 on your local system is free to host the redis container, else feel free to change the redis configuration on the docker-compose.
