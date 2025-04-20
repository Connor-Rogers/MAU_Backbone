# MAU_Backbone (Multi-Agent Utility Backbone)

A Model Context Protocol Server implementation for multi-agent travel booking.

## Overview

MAU_Backbone provides a framework for coordinating multiple specialized agents that work together to plan and book complete travel itineraries. The system can search for and book:

- Flights
- Hotels
- Local Experiences
- Transportation (car rentals, rideshares, public transit)

## Architecture

- **Model Context Protocol Server**: Core server managing agent communication and context
- **Agent System**: Specialized agents for different travel domains
- **External API Integration**: Connections to travel booking services
- **User Interface**: API for client applications to interact with the system

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Configure API keys in `.env`
3. Run the server: `python src/server.py`

## License

MIT