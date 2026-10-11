# Instagram AI chatbot

This project receives Instagram Direct messages through Meta webhooks, asks an
AI model to draft a reply, and sends the reply through the Instagram Messaging
API. The endpoints are designed for Vercel's Python Functions (`api/`). The
bot runs on the deployed host, so your laptop can be off.

## Configure Meta

1. Use an Instagram Business or Creator account. Connect a Facebook Page if
	required by the login/API flow you choose.
2. Create a Meta developer app and configure Instagram Messaging. Grant the
	permissions required for messaging and webhooks, including
	`instagram_manage_messages`; complete App Review before serving people who
	are not app-role testers.
3. Configure the webhook callback URL as `https://YOUR_DOMAIN/api/webhook`,
	use the same `VERIFY_TOKEN` value configured below, and subscribe to the
	Instagram `messages` webhook field.
4. In Instagram, allow the connected app to access messages under the account's
	message controls / connected tools settings.

## Enable memory

Create a Redis database in [Upstash](https://console.upstash.com/), then copy
its REST URL and REST token into the deployment environment variables below.
The app creates and expires conversation records automatically; no Redis
schema or local database file is needed.

## Environment variables

Set these in the deployment host's environment settings. Do not commit tokens
or secrets to the repository.

| Variable | Purpose |
| --- | --- |
| `VERIFY_TOKEN` | Secret string used when Meta verifies the webhook URL |
| `META_APP_SECRET` | Meta app secret used to verify webhook signatures |
| `INSTAGRAM_ACCESS_TOKEN` | Access token authorized for Instagram messaging in your selected login flow |
| `INSTAGRAM_ACCOUNT_ID` | Instagram professional account ID |
| `GROQ_API_KEY` | Groq API key used to generate replies |
| `GROQ_MODEL` | Optional Groq model ID; defaults to `llama-3.3-70b-versatile` |
| `BOT_SYSTEM_PROMPT` | Optional instructions that shape the bot's replies |
| `GRAPH_API_VERSION` | Optional Graph API version; defaults to `v26.0` |
| `CHAT_TEST_TOKEN` | Optional bearer token that enables the protected `/api/chat` test endpoint |
| `UPSTASH_REDIS_REST_URL` | HTTPS REST URL for an Upstash Redis database, required for memory |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST access token |

## Test

Deploy the project, then check `GET /api/webhook` verification in Meta's app
dashboard. The `GET /api/chat` endpoint reports whether the app is reachable.
To test AI generation directly, set `CHAT_TEST_TOKEN` and send an authorized
`POST /api/chat` request with JSON such as
`{"message":"Hello","conversation_id":"my-test-chat"}`. Reuse the same
`conversation_id` to continue that test conversation. A live DM test requires a
valid Meta token and a subscribed `messages` webhook.

The webhook currently handles text messages only. It ignores echoes and
non-text events. The latest 10 exchanges are stored per sender in Upstash Redis
and expire after 30 days without activity. For production use, add durable
message-ID deduplication and a queue so webhook retries or slow AI calls cannot
cause duplicate replies or exceed the hosting function's execution limit.
Message text and stored conversation history are sent to the configured AI
provider to generate each response. You can delete stored records from the
Upstash database if you need to clear conversation data sooner.