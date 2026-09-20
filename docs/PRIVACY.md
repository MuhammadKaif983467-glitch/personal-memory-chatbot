# Privacy

Privacy considerations for the Personal Memory Chatbot.

## Data Handling

The Personal Memory Chatbot processes potentially sensitive personal information. Users should understand how data is handled before use.

### Imported Data

- Conversation imports may contain highly personal information
- Imported data is stored locally in the SQLite database
- Imported content is treated as application data, not executable instructions
- Users should only import data they are authorized to process
- Import requires explicit consent confirmation

### AI Processing

- Chat messages and context are sent to the configured AI provider (OpenRouter by default)
- The AI provider may process prompts according to its own terms of service
- Provider selection affects data handling — review the provider's privacy policy
- The local heuristic provider processes data entirely offline

### Storage

- All data is stored locally in `data/chatbot.db`
- No data is sent to external services except the configured AI provider during chat
- Database files should be treated as sensitive
- Regular backups are recommended

### API Keys

- API keys must remain private
- Never commit `.env` to version control
- Never share API keys in logs, error messages, or responses
- Use separate keys for embeddings and chat when possible

## Recommendations

- Back up the database regularly
- Protect backup files with appropriate access controls
- Review imported content before confirming consent
- Use the local provider for development without sending data externally
- Rotate API keys periodically
- Do not import data you are not authorized to process

## Limitations

This application does not provide:
- End-to-end encryption
- HIPAA compliance
- GDPR compliance
- SOC 2 compliance
- Any regulatory compliance guarantees

Users are responsible for ensuring their use of this software complies with applicable laws and regulations.
