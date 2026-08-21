# Specification: Resilient Playlist and Cookie Handling Specification

## Change Identification
- **Change Name**: `resilient-playlist-and-cookie-handling`
- **Topic Key**: `sdd/resilient-playlist-and-cookie-handling/spec`
- **Target Subsystems**: `core.downloader`, `core.extractor`, `core.cookies`, `ui.console`, `youtube_downloader.cli`

---

## Domain Overview & Objectives
This specification defines the functional and operational requirements for robust, anti-fragile playlist downloading and cookie handling across diverse platforms (YouTube, TikTok, Instagram, Twitter/X, Twitch, etc.). The goal is to eliminate single-point failures caused by Windows Chromium database file locks, platform anti-bot burst detection, YouTube HTTP 403/poToken restrictions, and catastrophic playlist terminations.

---

## Requirements

### Requirement: REQ-01 Pacing and Jitter for Burst Prevention
The downloader MUST support request pacing with randomized jitter (`sleep_interval` and `max_sleep_interval`) across playlist and batch downloads to prevent automated burst detection and rate limiting.

#### Scenario: S-01.1 Configured sleep interval with randomized jitter between playlist items
- GIVEN a playlist download session configured with `--sleep-interval 3` and `--max-sleep-interval 7`
- WHEN the downloader completes item $N$ and prepares to process item $N+1$
- THEN the system MUST pause execution for a randomized duration $t$ where $3.0 \le t \le 7.0$ seconds before initiating the next network request.

#### Scenario: S-01.2 Default pacing behavior when flags are omitted
- GIVEN a playlist or batch download initiated without explicit sleep interval arguments
- WHEN sequential item requests are dispatched
- THEN the system SHOULD apply a default polite pacing interval with jitter (e.g., $1.0 \pm 0.5$ seconds) between distinct media items.

#### Scenario: S-01.3 Zero-sleep configuration (edge case)
- GIVEN a batch or playlist download configured with `--sleep-interval 0` and `--max-sleep-interval 0`
- WHEN subsequent items are processed
- THEN the system MUST proceed immediately without adding sleep pauses, respecting the user's explicit override.

---

### Requirement: REQ-02 YouTube Player Client Fallback Rotation
When YouTube extraction or stream download fails due to HTTP 403 Forbidden, bot challenges, poToken validation errors, or sign-in walls, the extractor and downloader MUST automatically cycle through fallback player clients (`ios`, `mweb`, `tv_embedded`, `android`, `web`) before failing.

#### Scenario: S-02.1 Automatic recovery on secondary player client upon 403 error
- GIVEN a YouTube media extraction request using the primary client (`android`/`web`) that fails with HTTP 403 or anti-bot verification
- WHEN the extractor detects the 403/bot exception
- THEN the extractor MUST rotate to the next candidate client in the fallback sequence (`ios`, `mweb`, `tv_embedded`), re-attempt extraction, and log an informational status message upon successful recovery.

#### Scenario: S-02.2 Exhaustion of all candidate clients (error state)
- GIVEN a YouTube video protected by stringent restrictions where all configured player clients fail with 403 or bot challenges
- WHEN all candidate clients in the rotation order have been attempted
- THEN the system MUST propagate a structured extraction failure indicating client exhaustion and trigger the error/recovery handling flow.

#### Scenario: S-02.3 Stream download client mismatch recovery
- GIVEN successful initial metadata extraction but a subsequent HTTP 403 error received during binary fragment/media streaming
- WHEN the media downloader detects the streaming HTTP 403 error
- THEN the downloader MUST re-extract streams using a fallback client profile and retry the stream download.

---

### Requirement: REQ-03 Lock-Safe Cookie Extraction on Windows Chromium Browsers
When extracting cookies from Chromium-based browsers (Brave, Chrome, Edge, Opera, Vivaldi) on Windows, the cookie manager MUST copy the SQLite database and encryption keys to a temporary location before reading to prevent file-lock conflicts while the browser is active, and MUST support browser profile specifiers (e.g. `brave:Default`, `chrome:Profile 1`).

#### Scenario: S-03.1 Active Chromium browser cookie extraction
- GIVEN an active running instance of Brave or Chrome holding an exclusive lock on its SQLite cookie database
- WHEN the user executes a command with `--cookies-from brave` or `--cookies-from chrome`
- THEN the cookie manager MUST create a temporary copy of the cookie database and associated key state, extract the valid session cookies from the copy without failing with file lock errors, and clean up temporary files upon completion.

#### Scenario: S-03.2 Profile specifier parsing and extraction
- GIVEN a Chromium browser with multiple user profiles (e.g. `Default`, `Profile 1`, `Profile 2`)
- WHEN the user passes `--cookies-from brave:Profile 1` or `--cookies-from chrome:Default`
- THEN the cookie manager MUST resolve the target profile subpath, copy the profile-specific database, and load cookies belonging to that specific profile.

#### Scenario: S-03.3 Invalid profile specifier handling (error state)
- GIVEN a specified profile name that does not exist in the browser user data directory (e.g. `chrome:NonExistentProfile`)
- WHEN cookie extraction is initialized
- THEN the system MUST report a clear error listing the available profiles detected on disk and fall back to the default profile or explicit cookie file cascade.

---

### Requirement: REQ-04 Playlist Download Resilience and Fault-Tolerant Queue Execution
In playlist and batch downloads, single video extraction or download failures MUST NOT terminate the entire playlist queue unless abort-on-error is explicitly enabled; the system MUST log the failure, retry with exponential backoff, and proceed to subsequent items.

#### Scenario: S-04.1 Single item failure resilience in playlist queue
- GIVEN a playlist containing 20 videos where item #5 is private, deleted, or blocked by DRM
- WHEN the playlist download is executed with default settings (`skip_errors=True`)
- THEN the downloader MUST record item #5 as failed with the error cause, increment the failed counter, and immediately proceed to download item #6 through #20 without terminating the process.

#### Scenario: S-04.2 Exponential backoff retry on transient network errors
- GIVEN a transient network timeout or connection reset during item #8 in a playlist
- WHEN the item download encounters a transient exception
- THEN the downloader MUST retry the item up to $N$ configured attempts with exponential backoff delay ($2^k \times \text{base delay}$) before marking it failed.

#### Scenario: S-04.3 Comprehensive post-execution audit summary
- GIVEN a playlist or batch download session containing a mix of successful, failed, and skipped items
- WHEN all items in the queue have been processed
- THEN the system MUST render a structured Rich summary table detailing the status (#, title/URL, status icon, reason/duration) and provide aggregate counts (total, succeeded, failed, skipped).

#### Scenario: S-04.4 Explicit abort-on-error override
- GIVEN a playlist download executed with `--no-skip-errors` or `--abort-on-error`
- WHEN an unrecoverable extraction or download error occurs on any item
- THEN the downloader MUST halt execution immediately and preserve the state of completed items in the download archive.

---

### Requirement: REQ-05 Interactive Recovery Handler
When an unrecoverable HTTP 403 Forbidden or bot challenge occurs during interactive CLI mode, the system MUST display a recovery menu providing the user with actionable options to retry without cookies, switch client or browser source, provide a cookie file, or skip the item.

#### Scenario: S-05.1 Interactive recovery menu presentation on 403 block
- GIVEN an interactive terminal session where automatic client rotation fails to bypass a 403/bot challenge
- WHEN the error occurs
- THEN the system MUST suspend execution and present a Rich prompt menu offering:
  1) Retry with alternate player client (e.g. `ios`, `mweb`, `tv_embedded`),
  2) Retry with different browser cookies (e.g. `brave`, `firefox`, `chrome`, `edge`) or without cookies,
  3) Specify custom cookie file path,
  4) Skip current item / Cancel.

#### Scenario: S-05.2 Successful user recovery action
- GIVEN the interactive recovery menu displayed on terminal
- WHEN the user selects "Retry with different browser cookies" and specifies `firefox`
- THEN the system MUST re-attempt the download with the new cookie source and continue the download if successful.

#### Scenario: S-05.3 Non-interactive mode bypass
- GIVEN a non-interactive execution (e.g. standard input piped, background batch script, or `--no-interactive` flag)
- WHEN an unrecoverable 403 or bot challenge occurs
- THEN the system MUST bypass the interactive recovery prompt, log the error diagnostic panel, and exit or skip according to resilience flags.

---

## Coverage Matrix
- **Happy Paths**:
  - S-01.1 (Configured sleep interval and jitter between playlist items)
  - S-01.2 (Default polite pacing in batch/playlist)
  - S-02.1 (Automatic fallback client rotation on 403)
  - S-03.1 (Lock-safe copy extraction for Chromium browsers)
  - S-03.2 (Chromium profile specifier support)
  - S-04.1 (Playlist queue continues past single item failures)
  - S-05.2 (Interactive user recovery selection)
- **Edge Cases**:
  - S-01.3 (Zero-sleep pacing override)
  - S-02.3 (Streaming HTTP 403 client mismatch recovery)
  - S-04.4 (Explicit abort-on-error flag)
  - S-05.3 (Non-interactive / automated execution bypass)
- **Error States**:
  - S-02.2 (Exhaustion of all candidate player clients)
  - S-03.3 (Invalid or missing browser profile specifier)
  - S-04.2 (Exponential backoff on transient network faults)
  - S-04.3 (Structured multi-item audit table on mixed failures)
  - S-05.1 (Prompt menu on unrecoverable bot challenge)

---

## Next Step
Ready for design (`sdd-design`).
