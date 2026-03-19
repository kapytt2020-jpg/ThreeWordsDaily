# ThreeWordsDaily - Known Issues and Solutions

## Overview

This document tracks known issues encountered during ThreeWordsDaily project development, their root causes, attempted solutions, and recommended fixes.

## Critical Issues

### 1. Admin Approval Workflow Timeout

**Status**: ⚠️ Long-standing issue

**Symptom**: Admin preview messages sometimes expire before admin can approve/edit, causing content to not be posted

**Root Cause**: 
- Fixed 25-minute wait window doesn't account for variable admin response times
- - No mechanism to retry or extend approval window
  - - n8n execution timeout policies may interrupt workflow
   
    - **Impact**:
    - - Daily content may not post on schedule
      - - Loss of content generation cycles
        - - User engagement drops
         
          - **Attempted Solutions**:
          - - Extended wait window from 15 to 25 minutes
            - - Added fallback automatic post after timeout
              - - Implemented admin notification retries
               
                - **Recommended Fix**:
                - ```javascript
                  // Implement dynamic timeout with retry logic
                  const checkApprovalStatus = async (contentId, maxWaitTime = 30) => {
                    const pollInterval = 2 * 60 * 1000; // 2 minutes
                    const startTime = Date.now();

                    while (Date.now() - startTime < maxWaitTime * 60 * 1000) {
                      const approval = await getApprovalStatus(contentId);
                      if (approval.status !== 'pending') {
                        return approval;
                      }
                      // Re-notify admin if still pending
                      if ((Date.now() - startTime) % (10 * 60 * 1000) === 0) {
                        await notifyAdminReminder(contentId);
                      }
                      await new Promise(resolve => setTimeout(resolve, pollInterval));
                    }
                    // Auto-post if still no response
                    return { status: 'auto-approved' };
                  };
                  ```

                  ---

                  ### 2. Message Formatting and Encoding Issues

                  **Status**: 🔴 Frequently Occurring

                  **Symptom**:
                  - Quiz messages with special characters fail to send
                  - - Emoji rendering issues on some clients
                    - - HTML/Markdown formatting inconsistencies
                     
                      - **Root Cause**:
                      - - OpenAI sometimes generates invalid Unicode sequences
                      - n8n message node doesn't properly escape special characters
                      - - Telegram API has specific formatting requirements
                       
                        - **Impact**:
                        - - Content displays with garbled text
                          - - Users cannot see quiz options properly
                            - - Test submissions fail
                             
                              - **Examples of Problematic Characters**:
                              - - Curly quotes: " " → Should be straight quotes: " "
                                - - Special dashes: – — → Should be hyphens: -
                                  - - Non-breaking spaces: \u00A0 → Should be regular spaces
                                   
                                    - **Solutions Implemented**:
                                    - 1. Added text sanitization layer in message formatting node
                                      2. 2. Used Unicode normalization (NFC) before sending
                                         3. 3. Implemented character-by-character validation
                                           
                                            4. **Code Solution**:
                                            5. ```javascript
                                               const sanitizeMessageText = (text) => {
                                                 return text
                                                   // Normalize Unicode
                                                   .normalize('NFC')
                                                   // Replace fancy quotes
                                                   .replace(/[""]/g, '"')
                                                   .replace(/['']/g, "'")
                                                   // Replace special dashes
                                                   .replace(/[–—]/g, '-')
                                                   // Remove zero-width characters
                                                   .replace(/\u200B/g, '')
                                                   // Replace non-breaking spaces
                                                   .replace(/\u00A0/g, ' ')
                                                   // Escape special characters for Telegram
                                                   .replace(/[_*\[\]()~`>#+-=|{}.!]/g, '\\$&');
                                               };
                                               ```

                                               ---

                                               ### 3. User Data Inconsistency Across Sheets

                                               **Status**: 🟡 Intermittent, difficult to debug

                                               **Symptom**:
                                               - User streak data doesn't match level data
                                               - - Points calculated incorrectly
                                                 - - Duplicate user records
                                                   - - Missing data after batch operations
                                                    
                                                     - **Root Cause**:
                                                     - - Multiple n8n nodes updating same user simultaneously
                                                       - - No transaction-like behavior in Google Sheets
                                                         - - Race conditions in concurrent updates
                                                           - - Insufficient data validation on append
                                                            
                                                             - **Long-Standing Challenge**:
                                                             - This has been the most challenging issue to resolve. The problem stems from the architecture where multiple workflow paths (daily word generation, user interaction handlers, streak calculations) can all update the same user records concurrently.
                                                            
                                                             - **Impact**:
                                                             - - Incorrect leaderboard rankings
                                                               - - User frustration with missing progress
                                                                 - - Admin confusion when reviewing data
                                                                   - - Difficult data recovery
                                                                    
                                                                     - **Solutions Attempted**:
                                                                     - 1. ❌ Sequential processing: Too slow, missed processing windows
                                                                       2. 2. ❌ Locks in Google Sheets: Not supported natively
                                                                          3. 3. ✅ Batch updates with merge: Works but requires cleanup
                                                                             4. 4. Partial: Deduplication script (works but manual)
                                                                               
                                                                                5. **Recommended Comprehensive Solution**:
                                                                                6. ```javascript
                                                                                   // Implement write-ahead logging and merge strategy
                                                                                   const updateUserDataAtomic = async (userId, updates) => {
                                                                                     const timestamp = Date.now();

                                                                                     // Step 1: Write to temporary log
                                                                                     await sheets.append('data_log', [{
                                                                                       user_id: userId,
                                                                                       operation: JSON.stringify(updates),
                                                                                       timestamp: timestamp,
                                                                                       status: 'pending'
                                                                                     }]);

                                                                                     // Step 2: Get current data
                                                                                     const currentData = await sheets.getRow('user_data', userId);

                                                                                       // Step 3: Merge new data
                                                                                     const mergedData = {
                                                                                       ...currentData,
                                                                                       ...updates,
                                                                                       last_updated: timestamp
                                                                                     };

                                                                                     // Step 4: Write merged data
                                                                                     await sheets.upsertRow('user_data', mergedData);

                                                                                     // Step 5: Mark log as committed
                                                                                     await sheets.update('data_log', timestamp, { status: 'committed' });

                                                                                     return mergedData;
                                                                                   };
                                                                                   ```

                                                                                   ---

                                                                                   ### 4. API Rate Limiting

                                                                                   **Status**: 🟡 Occasional, under peak load

                                                                                   **Symptom**:
                                                                                   - OpenAI API 429 (Too Many Requests) errors
                                                                                   - - Telegram API rate limit hits
                                                                                     - - SerpAPI quota exceeded
                                                                                      
                                                                                       - **Root Cause**:
                                                                                       - - Multiple scheduled triggers firing simultaneously
                                                                                         - - No rate limiting queue implemented in n8n
                                                                                           - - Test content generation increases API calls
                                                                                             - - Growth agent continuously searching
                                                                                              
                                                                                               - **Impact**:
                                                                                               - - Delayed message delivery
                                                                                                 - - Failed content generation
                                                                                                   - - Missing opportunity notifications
                                                                                                     - - Cost overruns on API usage
                                                                                                      
                                                                                                       - **Solutions Implemented**:
                                                                                                       - 1. Added exponential backoff retry logic
                                                                                                         2. 2. Implemented request queuing in n8n
                                                                                                            3. 3. Added API key rotation between requests
                                                                                                               4. 4. Scheduled staggered triggers
                                                                                                                 
                                                                                                                  5. **Code Solution**:
                                                                                                                  6. ```javascript
                                                                                                                     const callOpenAIWithRateLimit = async (prompt, model = 'gpt-4') => {
                                                                                                                       const maxRetries = 3;
                                                                                                                       const baseDelay = 1000; // 1 second

                                                                                                                       for (let attempt = 0; attempt < maxRetries; attempt++) {
                                                                                                                         try {
                                                                                                                           return await openai.createChatCompletion({
                                                                                                                             model: model,
                                                                                                                             messages: [{ role: 'user', content: prompt }],
                                                                                                                             temperature: 0.7,
                                                                                                                             max_tokens: 500
                                                                                                                           });
                                                                                                                         } catch (error) {
                                                                                                                           if (error.response?.status === 429) {
                                                                                                                             const delay = baseDelay * Math.pow(2, attempt);
                                                                                                                             const waitTime = error.response?.headers['retry-after']
                                                                                                                               ? parseInt(error.response.headers['retry-after']) * 1000
                                                                                                                               : delay;

                                                                                                                             await new Promise(resolve => setTimeout(resolve, waitTime));
                                                                                                                             continue;
                                                                                                                           }
                                                                                                                           throw error;
                                                                                                                         }
                                                                                                                       }
                                                                                                                       throw new Error('Max retries exceeded for OpenAI API');
                                                                                                                     };
                                                                                                                     ```
                                                                                                                     
                                                                                                                     ---
                                                                                                                     
                                                                                                                     ### 5. Duplicate Message Processing
                                                                                                                     
                                                                                                                     **Status**: 🟡 Intermittent but critical
                                                                                                                     
                                                                                                                     **Symptom**:
                                                                                                                     - Users receive duplicate messages
                                                                                                                     - - Multiple processing of same button click
                                                                                                                       - - Streak incremented multiple times
                                                                                                                        
                                                                                                                         - **Root Cause**:
                                                                                                                         - - Webhook retries from Telegram
                                                                                                                           - - No idempotency token checking
                                                                                                                             - - Race conditions in message processing
                                                                                                                               - - n8n execution retries without deduplication
                                                                                                                                
                                                                                                                                 - **Impact**:
                                                                                                                                 - - User confusion
                                                                                                                                   - - Artificial score inflation
                                                                                                                                     - - Data corruption
                                                                                                                                       - - Poor user experience
                                                                                                                                        
                                                                                                                                         - **Solutions Implemented**:
                                                                                                                                         - 1. Added message ID deduplication
                                                                                                                                           2. 2. Implemented request ID tracking
                                                                                                                                              3. 3. Added processing state tracking
                                                                                                                                              
                                                                                                                                              **Code Solution**:
                                                                                                                                              ```javascript
                                                                                                                                              const processUserMessage = async (message) => {
                                                                                                                                                const messageKey = `${message.chat_id}_${message.message_id}_${message.date}`;

                                                                                                                                                // Check if already processed
                                                                                                                                                const processedKey = await redis.get(`processed_${messageKey}`);
                                                                                                                                                if (processedKey) {
                                                                                                                                                  console.log('Duplicate message, skipping');
                                                                                                                                                  return { status: 'duplicate', processed: true };
                                                                                                                                                }

                                                                                                                                                try {
                                                                                                                                                  // Process message
                                                                                                                                                  const result = await handleUserMessage(message);
                                                                                                                                                  
                                                                                                                                                      // Mark as processed
                                                                                                                                                          await redis.setex(`processed_${messageKey}`, 3600, '1'); // 1 hour TTL

                                                                                                                                                  return { status: 'success', data: result };
                                                                                                                                                } catch (error) {
                                                                                                                                                  // Don't mark as processed on error - allow retry
                                                                                                                                                  throw error;
                                                                                                                                                }
                                                                                                                                              };
                                                                                                                                              ```
                                                                                                                                              
                                                                                                                                              ---
                                                                                                                                              
                                                                                                                                              ## Medium Priority Issues
                                                                                                                                              
                                                                                                                                              ### 6. TTS Audio Generation Failures
                                                                                                                                              
                                                                                                                                              **Status**: 🟡 Occasional failures
                                                                                                                                              
                                                                                                                                              **Issue**: Voice message generation sometimes fails silently
                                                                                                                                              - OpenAI TTS API timeouts
                                                                                                                                              - - File size exceeding Telegram limits (50MB)
                                                                                                                                                - - Unsupported characters in text
                                                                                                                                                 
                                                                                                                                                  - **Solution**: Implement fallback text-only messages and TTS try/catch blocks
                                                                                                                                                 
                                                                                                                                                  - ---
                                                                                                                                                  
                                                                                                                                                  ### 7. Leaderboard Calculation Errors
                                                                                                                                                  
                                                                                                                                                  **Status**: 🟡 Weekly sync issues
                                                                                                                                                  
                                                                                                                                                  **Issue**: Top 10 leaderboard sometimes includes inactive users
                                                                                                                                                  - Stale data from cached sheets
                                                                                                                                                  - - Missing user_points entries
                                                                                                                                                    - - Date filtering logic errors
                                                                                                                                                     
                                                                                                                                                      - **Solution**: Implement data validation before leaderboard generation
                                                                                                                                                     
                                                                                                                                                      - ---
                                                                                                                                                      
                                                                                                                                                      ### 8. Growth Agent Search Results Relevance
                                                                                                                                                      
                                                                                                                                                      **Status**: 🟡 Low relevance matches
                                                                                                                                                      
                                                                                                                                                      **Issue**: SerpAPI returning irrelevant partnership opportunities
                                                                                                                                                      - Search query too broad
                                                                                                                                                      - - No filtering of results
                                                                                                                                                        - - Outdated API response handling
                                                                                                                                                         
                                                                                                                                                          - **Solution**: Add result relevance scoring and manual whitelist of quality partners
                                                                                                                                                         
                                                                                                                                                          - ---
                                                                                                                                                          
                                                                                                                                                          ## Low Priority Issues
                                                                                                                                                          
                                                                                                                                                          ### 9. Admin Interface Responsiveness
                                                                                                                                                          - Admin buttons sometimes unresponsive
                                                                                                                                                          - - Solution: Add confirmation receipt to admin
                                                                                                                                                           
                                                                                                                                                            - ### 10. Incorrect Timezone Handling
                                                                                                                                                            - - User timestamps not converting correctly
                                                                                                                                                              - - Solution: Standardize all times to UTC
                                                                                                                                                               
                                                                                                                                                                - ---
                                                                                                                                                                
                                                                                                                                                                ## Testing & Validation
                                                                                                                                                                
                                                                                                                                                                ### Recommended Test Cases for Each Issue:
                                                                                                                                                                
                                                                                                                                                                **Issue #1 (Admin Timeout)**:
                                                                                                                                                                - Test with 30-minute wait and manual delay
                                                                                                                                                                - - Verify auto-post triggers correctly
                                                                                                                                                                  - - Check notification retries send
                                                                                                                                                                   
                                                                                                                                                                    - **Issue #2 (Message Formatting)**:
                                                                                                                                                                    - - Test with all Unicode characters from test suite
                                                                                                                                                                      - - Verify emoji rendering on iOS, Android, Web
                                                                                                                                                                        - - Check Telegram API formatting compliance
                                                                                                                                                                         
                                                                                                                                                                          - **Issue #3 (Data Inconsistency)**:
                                                                                                                                                                          - - Run concurrent update stress test (100 simultaneous updates)
                                                                                                                                                                            - - Verify merge strategy doesn't lose data
                                                                                                                                                                              - - Check deduplication script effectiveness
                                                                                                                                                                               
                                                                                                                                                                                - **Issue #4 (Rate Limiting)**:
                                                                                                                                                                                - - Load test with 10x normal API volume
                                                                                                                                                                                  - - Verify exponential backoff waits correctly
                                                                                                                                                                                    - - Check queue doesn't overflow
                                                                                                                                                                                     
                                                                                                                                                                                      - **Issue #5 (Duplicates)**:
                                                                                                                                                                                      - - Simulate Telegram webhook retries
                                                                                                                                                                                        - - Verify message ID tracking works
                                                                                                                                                                                          - - Test with multiple concurrent messages
                                                                                                                                                                                           
                                                                                                                                                                                            - ---
                                                                                                                                                                                            
                                                                                                                                                                                            ## Monitoring & Prevention
                                                                                                                                                                                            
                                                                                                                                                                                            ### Recommended Monitoring:
                                                                                                                                                                                            1. Set up alerts for API error rates > 5%
                                                                                                                                                                                            2. 2. Monitor sheet write latency
                                                                                                                                                                                               3. 3. Track duplicate message detection rate
                                                                                                                                                                                                  4. 4. Monitor queue depth in n8n
                                                                                                                                                                                                    
                                                                                                                                                                                                     5. ### Prevention Strategies:
                                                                                                                                                                                                     6. 1. Implement comprehensive error logging
                                                                                                                                                                                                        2. 2. Add automated data validation checks
                                                                                                                                                                                                           3. 3. Implement health checks for all integrations
                                                                                                                                                                                                              4. 4. Regular backup of user data
                                                                                                                                                                                                                 5. 5. Staging environment testing before production
                                                                                                                                                                                                                   
                                                                                                                                                                                                                    6. ---
                                                                                                                                                                                                                   
                                                                                                                                                                                                                    7. ## Resolution Timeline
                                                                                                                                                                                                                   
                                                                                                                                                                                                                    8. | Issue | Reported | Status | ETA |
                                                                                                                                                                                                                    9. |-------|----------|--------|-----|
                                                                                                                                                                                                                    10. | Admin Timeout | Jan 2026 | In Progress | Mar 2026 |
                                                                                                                                                                                                                    11. | Message Formatting | Jan 2026 | Resolved (70%) | Ongoing |
                                                                                                                                                                                                                    12. | Data Inconsistency | Dec 2025 | Partially Resolved | Apr 2026 |
                                                                                                                                                                                                                    13. | Rate Limiting | Feb 2026 | Resolved | Implemented |
                                                                                                                                                                                                                    14. | Duplicates | Ongoing | Monitoring | Ongoing |
                                                                                                                                                                                                                   
                                                                                                                                                                                                                    15. ---
                                                                                                                                                                                                                   
                                                                                                                                                                                                                    16. **Last Updated**: March 2026
                                                                                                                                                                                                                    17. **Maintained By**: Project Team
                                                                                                                                                                                                                    18. **Next Review**: April 2026
