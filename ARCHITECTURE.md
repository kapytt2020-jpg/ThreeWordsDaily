# ThreeWordsDaily - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Telegram Users                            │
│  (via @ThreeWordsDaily, @YourBot_test_bot, etc.)       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────────┐
         │   Telegram API    │
         │    Webhooks       │
         └─────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   ┌─────────┐          ┌──────────────┐
   │   n8n   │◄────────►│  OpenAI API  │
   │Workflow │          │  (GPT-4)     │
   │Engine   │          └──────────────┘
   └────┬────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────────┐  ┌─────────────┐   ┌──────────────┐
   │ Google      │  │   SerpAPI   │   │ Local Llama  │
   │ Sheets      │  │  (Search)   │   │ (Optional)   │
   └─────────────┘  └─────────────┘   └──────────────┘
```

## Component Breakdown

### 1. Entry Points (Triggers)

#### Schedule Triggers
- **Daily 9:00 AM**: Word generation and test
- - **Daily 10:00 AM**: User engagement check
  - - **Daily 7:00 PM**: Evening content
    - - **Daily 8:00 PM**: Streak reminders
      - - **Weekly (Mon-Fri)**: Challenge posts
        - - **Sunday 6:00 PM**: Poll generation
          - - **Sunday 7:00 PM**: Weekly recap
           
            - #### Webhook Triggers
            - - **Telegram Messages**: Multiple bot webhooks for:
              -   - Test Bot (@YourBot_test_bot)
                  -   - Production Bot (@YourBot_prod_bot)
                      -   - PR Bot (@SpeakBetter_bot)
                          -   - Teacher Bot (@YourBrand_group_teacher_bot)
                           
                              - #### Manual Triggers
                              - - Testing nodes for development
                                - - Admin actions
                                 
                                  - ### 2. Core Processing Nodes
                                 
                                  - #### Message Routing
                                  - ```
                                    User Message → [Command Router] →  Multiple Paths:
                                        ├─ /speak    → Conversation Mode
                                        ├─ /test     → Level Test Handler
                                        ├─ /stats    → Statistics Generator
                                        ├─ /top10    → Leaderboard Generator
                                        ├─ /help     → Help Message
                                        ├─ /word     → Word of Day
                                        └─ /quiz     → Quiz Handler
                                    ```

                                    #### Content Generation Pipeline
                                    ```
                                    [Schedule Trigger]
                                        ↓
                                    [Content Type Selector] → Random selection
                                        ↓
                                    [OpenAI - Content Generator] → GPT-4 API call
                                        ↓
                                    [Format Message] → HTML/Markdown formatting
                                        ↓
                                    [Admin Preview] → Send to admin for approval
                                        ↓
                                    [Wait for Admin] → 25-minute timeout
                                        ↓
                                    [Admin Router] → Approve/Edit/Skip/Regenerate
                                        ↓
                                    [Post to Channel] → sendMessage to @ThreeWordsDaily
                                    ```

                                    ### 3. Data Flow

                                    #### User Data Schema

                                    ```json
                                    {
                                      "user_streaks": {
                                        "user_id": string,
                                        "streak_count": number,
                                        "last_message_date": date,
                                        "achievement_level": string
                                      },
                                      "user_levels": {
                                        "user_id": string,
                                        "current_level": number,
                                        "test_passed": boolean,
                                        "points": number
                                      },
                                      "user_points": {
                                        "user_id": string,
                                        "daily_points": number,
                                        "weekly_points": number,
                                        "total_points": number
                                      },
                                      "used_words": {
                                        "word": string,
                                        "user_id": string,
                                        "date_used": date,
                                        "category": string
                                      },
                                      "user_mistakes": {
                                        "user_id": string,
                                        "word": string,
                                        "mistake_type": string,
                                        "count": number,
                                        "patterns": array
                                      }
                                    }
                                    ```

                                    #### Data Operations
                                    - **Create**: Upsert operations on user data
                                    - - **Read**: Get user data, get all users
                                      - - **Update**: Append streak, level, points
                                        - - **Merge**: Combine multiple user data records
                                          - - **Clean**: Duplicate detection and removal
                                           
                                            - ### 4. AI Integration
                                           
                                            - #### OpenAI GPT-4 Usage
                                           
                                            - **Instances:**
                                            - 1. **Main Content Generation**
                                              2.    - Daily word selection
                                                    -    - Quiz generation
                                                         -    - Content formatting
                                                              -    - Fun facts
                                                               
                                                                   - 2. **User Response Handling**
                                                                     3.    - Conversation responses
                                                                           -    - Test answers evaluation
                                                                                -    - Mistake analysis
                                                                                 
                                                                                     - 3. **Growth Agent**
                                                                                       4.    - Partnership opportunity search
                                                                                             -    - Content idea generation
                                                                                              
                                                                                                  - 4. **Specialized Bots**
                                                                                                    5.    - PR Bot responses
                                                                                                          -    - Teacher Bot responses
                                                                                                           
                                                                                                               - #### Prompt Engineering
                                                                                                               - - System instructions for each role
                                                                                                                 - - Context from user data
                                                                                                                   - - Temperature settings for creativity
                                                                                                                     - - Max tokens for response length
                                                                                                                      
                                                                                                                       - ### 5. External Integrations
                                                                                                                      
                                                                                                                       - #### Telegram Bot API
                                                                                                                       - - Multiple bot instances
                                                                                                                         - - Message sending (sendMessage)
                                                                                                                           - - Audio/voice messages (sendAudio)
                                                                                                                             - - TTS integration
                                                                                                                               - - Button/inline keyboard support
                                                                                                                                 - - Callback query handling
                                                                                                                                  
                                                                                                                                   - #### Google Sheets
                                                                                                                                   - - Real-time user data sync
                                                                                                                                     - - Append operations for new entries
                                                                                                                                       - - Batch updates
                                                                                                                                         - - Data validation
                                                                                                                                          
                                                                                                                                           - #### SerpAPI
                                                                                                                                           - - Daily brand partnership search
                                                                                                                                             - - Google search integration
                                                                                                                                               - - Results processing
                                                                                                                                                 - - Email notification to admin
                                                                                                                                                  
                                                                                                                                                   - #### Local Services
                                                                                                                                                   - - Llama instance (localhost:11434)
                                                                                                                                                     - - Alternative to OpenAI for certain tasks
                                                                                                                                                       - - HTTP POST requests
                                                                                                                                                        
                                                                                                                                                         - ### 6. Feature Modules
                                                                                                                                                        
                                                                                                                                                         - #### Achievement System
                                                                                                                                                         - ```
                                                                                                                                                           [Streak Calculation]
                                                                                                                                                               ↓
                                                                                                                                                           [Milestone Check] → Achievement unlocked?
                                                                                                                                                               ↓
                                                                                                                                                           [Points Award] → Bonus points
                                                                                                                                                               ↓
                                                                                                                                                           [Notification] → Send to user
                                                                                                                                                           ```
                                                                                                                                                           
                                                                                                                                                           #### Leaderboard System
                                                                                                                                                           ```
                                                                                                                                                           [Top 10 Query] → Query user_points table
                                                                                                                                                               ↓
                                                                                                                                                           [Format Data] → Create ranking
                                                                                                                                                               ↓
                                                                                                                                                           [Generate Message] → Visual format
                                                                                                                                                               ↓
                                                                                                                                                           [Post Weekly] → Every Sunday
                                                                                                                                                           ```
                                                                                                                                                           
                                                                                                                                                           #### Quiz System
                                                                                                                                                           ```
                                                                                                                                                           [Generate Questions] → OpenAI API
                                                                                                                                                               ↓
                                                                                                                                                           [Format Quiz] → Inline buttons
                                                                                                                                                               ↓
                                                                                                                                                           [Send to User]
                                                                                                                                                               ↓
                                                                                                                                                           [Collect Answers] → Button callbacks
                                                                                                                                                               ↓
                                                                                                                                                           [Evaluate] → Check correctness
                                                                                                                                                               ↓
                                                                                                                                                           [Feedback] → Mistake analysis
                                                                                                                                                           ```
                                                                                                                                                           
                                                                                                                                                           ### 7. Approval Workflow
                                                                                                                                                           
                                                                                                                                                           ```
                                                                                                                                                           [Admin Preview Generated]
                                                                                                                                                               ↓
                                                                                                                                                           [Send with Action Buttons]
                                                                                                                                                               ├─ Approve
                                                                                                                                                               ├─ Edit (Request changes)
                                                                                                                                                               ├─ Skip
                                                                                                                                                               └─ Regenerate
                                                                                                                                                               ↓
                                                                                                                                                           [Wait 25 Minutes]
                                                                                                                                                               ↓
                                                                                                                                                           [Admin Router]
                                                                                                                                                               ├─ Approve → Post immediately
                                                                                                                                                               ├─ Edit → Ask for changes, wait for new version
                                                                                                                                                               ├─ Skip → Store for later review
                                                                                                                                                               └─ Regenerate → Create new content
                                                                                                                                                           ```
                                                                                                                                                           
                                                                                                                                                           ### 8. Error Handling
                                                                                                                                                           
                                                                                                                                                           #### Retry Logic
                                                                                                                                                           - OpenAI API failures → Retry up to 3 times
                                                                                                                                                           - - Telegram delivery → Confirm receipt
                                                                                                                                                             - - Sheet operations → Transaction-like behavior
                                                                                                                                                              
                                                                                                                                                               - #### Fallback Mechanisms
                                                                                                                                                               - - Use cached content if generation fails
                                                                                                                                                                 - - Use alternative AI model if primary fails
                                                                                                                                                                   - - Manual admin override options
                                                                                                                                                                    
                                                                                                                                                                     - #### Logging
                                                                                                                                                                     - - Execution logs in n8n dashboard
                                                                                                                                                                       - - Error notifications to admin
                                                                                                                                                                         - - User action tracking for debugging
                                                                                                                                                                          
                                                                                                                                                                           - ## Database Schema
                                                                                                                                                                          
                                                                                                                                                                           - ### Google Sheets Tables
                                                                                                                                                                           - 1. **user_streaks** - User daily streak data
                                                                                                                                                                             2. 2. **user_levels** - User skill level progression
                                                                                                                                                                                3. 3. **user_points** - User point accumulation
                                                                                                                                                                                   4. 4. **used_words** - Word usage history
                                                                                                                                                                                      5. 5. **user_mistakes** - Mistake patterns and analysis
                                                                                                                                                                                        
                                                                                                                                                                                         6. ## Deployment Considerations
                                                                                                                                                                                        
                                                                                                                                                                                         7. ### Environment Variables
                                                                                                                                                                                         8. ```
                                                                                                                                                                                            OPENAI_API_KEY=<key>
                                                                                                                                                                                            TELEGRAM_BOT_TOKEN_TEST=<token>
                                                                                                                                                                                            TELEGRAM_BOT_TOKEN_PROD=<token>
                                                                                                                                                                                            TELEGRAM_BOT_TOKEN_PR=<token>
                                                                                                                                                                                            TELEGRAM_BOT_TOKEN_TEACHER=<token>
                                                                                                                                                                                            SERPAPI_KEY=<key>
                                                                                                                                                                                            GOOGLE_SHEETS_ID=<id>
                                                                                                                                                                                            WEBHOOK_URL=<url>
                                                                                                                                                                                            ```
                                                                                                                                                                                            
                                                                                                                                                                                            ### Infrastructure Requirements
                                                                                                                                                                                            - n8n instance (CPU: 2+ cores, RAM: 2GB+ minimum)
                                                                                                                                                                                            - - Stable internet connection
                                                                                                                                                                                              - - Webhook URL publicly accessible
                                                                                                                                                                                                - - HTTPS for Telegram webhooks
                                                                                                                                                                                                 
                                                                                                                                                                                                  - ### Scaling Considerations
                                                                                                                                                                                                  - - User base > 10,000: Consider database optimization
                                                                                                                                                                                                    - - Message volume > 50,000/day: Implement queue system
                                                                                                                                                                                                      - - Multiple bots: Centralized credential management
                                                                                                                                                                                                       
                                                                                                                                                                                                        - ## Performance Metrics
                                                                                                                                                                                                       
                                                                                                                                                                                                        - ### Expected Latency
                                                                                                                                                                                                        - - Message delivery: < 2 seconds
                                                                                                                                                                                                          - - Quiz generation: 5-10 seconds
                                                                                                                                                                                                            - - Admin notification: < 1 second
                                                                                                                                                                                                              - - Statistics calculation: < 5 seconds
                                                                                                                                                                                                               
                                                                                                                                                                                                                - ### Throughput
                                                                                                                                                                                                                - - Concurrent users: 1,000+
                                                                                                                                                                                                                  - - Messages/hour: 10,000+
                                                                                                                                                                                                                    - - API calls/minute: 100+
                                                                                                                                                                                                                     
                                                                                                                                                                                                                      - ## Security
                                                                                                                                                                                                                     
                                                                                                                                                                                                                      - ### API Keys Protection
                                                                                                                                                                                                                      - - Environment variables for secrets
                                                                                                                                                                                                                        - - n8n credentials encryption
                                                                                                                                                                                                                          - - Regular key rotation
                                                                                                                                                                                                                           
                                                                                                                                                                                                                            - ### User Data Privacy
                                                                                                                                                                                                                            - - No PII stored beyond username/ID
                                                                                                                                                                                                                              - - GDPR compliance considerations
                                                                                                                                                                                                                                - - Data retention policies
                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                  - ### Bot Authentication
                                                                                                                                                                                                                                  - - Webhook signature verification
                                                                                                                                                                                                                                    - - Rate limiting per user
                                                                                                                                                                                                                                      - - Spam detection
                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                        - ---
                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                        **Last Updated**: March 2026
                                                                                                                                                                                                                                        **Version**: 1.0
