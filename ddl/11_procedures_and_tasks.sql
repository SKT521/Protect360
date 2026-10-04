-- ============================================================
-- Stored Procedures and Tasks
-- ============================================================

CREATE OR REPLACE PROCEDURE PROTECT360_DB.SILVER.SP_PROCESS_INTERACTION_SIGNALS()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
'BEGIN
    LET row_count INTEGER;

    INSERT INTO PROTECT360_DB.SILVER.INTERACTION_AI_SIGNAL
        (SIGNAL_SK, INTERACTION_SK, CUSTOMER_ID, SENTIMENT_LABEL, SENTIMENT_SCORE,
         INTENT_LABEL, PRICE_SENSITIVITY_FLAG, KEY_CONCERNS_SUMMARY, MODEL_NAME, PROMPT_VERSION, PROCESSED_TS)
    SELECT
        MD5(i.INTERACTION_SK || ''::v1'') AS SIGNAL_SK,
        i.INTERACTION_SK,
        i.CUSTOMER_ID,
        TRY_PARSE_JSON(resp):sentiment_label::VARCHAR       AS SENTIMENT_LABEL,
        TRY_PARSE_JSON(resp):sentiment_score::NUMBER(4,2)   AS SENTIMENT_SCORE,
        TRY_PARSE_JSON(resp):intent_label::VARCHAR          AS INTENT_LABEL,
        TRY_PARSE_JSON(resp):price_sensitivity_flag::BOOLEAN AS PRICE_SENSITIVITY_FLAG,
        TRY_PARSE_JSON(resp):key_concerns_summary::VARCHAR  AS KEY_CONCERNS_SUMMARY,
        ''llama3.1-70b''  AS MODEL_NAME,
        ''v1.0''          AS PROMPT_VERSION,
        CURRENT_TIMESTAMP() AS PROCESSED_TS
    FROM PROTECT360_DB.SILVER.CUSTOMER_INTERACTION i
    CROSS JOIN LATERAL (
        SELECT SNOWFLAKE.CORTEX.TRY_COMPLETE(
            ''llama3.1-70b'',
            ''Analyse this insurance customer interaction transcript and return a JSON object with exactly these fields: {"sentiment_label": "POSITIVE or NEUTRAL or NEGATIVE", "sentiment_score": number between -1.0 and 1.0, "intent_label": "ENQUIRY or QUOTE or RENEWAL or CLAIM or COMPLAINT or RETENTION or CANCELLATION", "price_sensitivity_flag": true or false, "key_concerns_summary": "one sentence summary"} Only output the JSON object, nothing else. Transcript: '' || i.TRANSCRIPT_TEXT
        ) AS resp
    ) llm
    WHERE i.TRANSCRIPT_TEXT IS NOT NULL
      AND i.TRANSCRIPT_TEXT != ''''
      AND i.INTERACTION_SK NOT IN (SELECT INTERACTION_SK FROM PROTECT360_DB.SILVER.INTERACTION_AI_SIGNAL);

    row_count := SQLROWCOUNT;
    RETURN ''Processed '' || :row_count || '' interactions'';
END';


CREATE OR REPLACE TASK PROTECT360_DB.SILVER.TASK_PROCESS_AI_SIGNALS
    WAREHOUSE = CORTEX_WH
    SCHEDULE = 'USING CRON 0 6 * * * Australia/Sydney'
    COMMENT = 'Processes interaction transcripts through Cortex LLM for sentiment and intent extraction'
AS
    CALL PROTECT360_DB.SILVER.SP_PROCESS_INTERACTION_SIGNALS();
