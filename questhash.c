/*
 * questhash.c  —  Vault Zero native C extension
 * Language    : C
 * Compiled to : questhash.so  (Linux) / questhash.dll (Windows)
 * Called by   : lua_bridge.py via ctypes  AND  quests/events.lua via ffi
 *
 * Provides:
 *   uint32_t hash_puzzle_id(const char* room, const char* puzzle)
 *   uint32_t hash_player_run(const char* username, uint32_t elapsed_s)
 *   int      verify_code(const char* input, const char* answer)
 *   void     get_run_token(const char* username, uint32_t ts, char* out, int out_len)
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

/* ── FNV-1a 32-bit hash ─────────────────────────────────────────────────── */
static uint32_t fnv1a(const char *data, size_t len) {
    uint32_t hash = 0x811c9dc5u;
    for (size_t i = 0; i < len; i++) {
        hash ^= (uint8_t)data[i];
        hash *= 0x01000193u;
    }
    return hash;
}

/* ── Public API ─────────────────────────────────────────────────────────── */

/*
 * hash_puzzle_id — deterministic ID for a room+puzzle pair
 * Returns a 32-bit hash used as the puzzle's canonical event ID.
 */
uint32_t hash_puzzle_id(const char *room, const char *puzzle) {
    char buf[256];
    snprintf(buf, sizeof(buf), "%s::%s", room ? room : "", puzzle ? puzzle : "");
    return fnv1a(buf, strlen(buf));
}

/*
 * hash_player_run — unique token for a player's run at a given timestamp
 */
uint32_t hash_player_run(const char *username, uint32_t elapsed_s) {
    char buf[256];
    snprintf(buf, sizeof(buf), "%s::%u", username ? username : "", elapsed_s);
    return fnv1a(buf, strlen(buf));
}

/*
 * verify_code — constant-time string comparison (prevents timing attacks)
 * Returns 1 if match, 0 if not.
 */
int verify_code(const char *input, const char *answer) {
    if (!input || !answer) return 0;
    size_t la = strlen(input), lb = strlen(answer);
    size_t maxlen = la > lb ? la : lb;
    int diff = 0;
    for (size_t i = 0; i < maxlen; i++) {
        char a = i < la ? input[i]  : 0;
        char b = i < lb ? answer[i] : 0;
        /* case-insensitive */
        if (a >= 'A' && a <= 'Z') a += 32;
        if (b >= 'A' && b <= 'Z') b += 32;
        diff |= (a ^ b);
    }
    return diff == 0 ? 1 : 0;
}

/*
 * get_run_token — write a short hex token string into out
 * Format: <8-char hex hash>-<elapsed_s>
 */
void get_run_token(const char *username, uint32_t elapsed_s, char *out, int out_len) {
    if (!out || out_len < 16) return;
    uint32_t h = hash_player_run(username, elapsed_s);
    snprintf(out, out_len, "%08x-%u", h, elapsed_s);
}

/* ── CLI entry point (when run directly) ───────────────────────────────── */
#ifdef QUESTHASH_MAIN
int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "usage: questhash <room> <puzzle>\n");
        fprintf(stderr, "       questhash verify <input> <answer>\n");
        return 1;
    }
    if (strcmp(argv[1], "verify") == 0 && argc == 4) {
        int ok = verify_code(argv[2], argv[3]);
        printf("%s\n", ok ? "MATCH" : "NOMATCH");
        return ok ? 0 : 1;
    }
    uint32_t id = hash_puzzle_id(argv[1], argv[2]);
    char token[64];
    get_run_token(argv[1], id, token, sizeof(token));
    printf("puzzle_id : %u (0x%08x)\n", id, id);
    printf("run_token : %s\n", token);
    return 0;
}
#endif
