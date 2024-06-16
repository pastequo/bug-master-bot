# BugMasterBot

A Slack bot designed to manage `PROW` failures in the `Slack` CI channel. Its primary functionalities are divided into two components:

## 1. Event Listener

`BugMasterBot` continuously listens to events in the Slack channel via the `slack` events webhook. This feature is encapsulated within the `events` directory. Primarily, it:
- Receives notifications about messages sent in the channel pertaining to a failed CI job.
- Conducts a thorough analysis of the failure.
- Responds directly to the concerning message with a comprehensive report.

## 2. Action Responder

`BugMasterBot` also responds to user-initiated actions in the Slack channel, specifically those triggered using Slack's slash commands. This feature resides in the `commands` directory. Currently, it supports a range of commands:

- `config`: Fetches the configuration file used in the channel.
- `help`: Provides detailed guidelines on utilizing the but effectively.
- `apply`: Implements BugMasterBot's logic on the last 'n' messages in the channel (default is set to 20).
- `filterby`: Allows users to filter out failed jobs based on specific criteria.
- `jobinfo`: Retrieves the latest status of job records.
