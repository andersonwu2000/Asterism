"""
spike-007: claude CLI prompt token upper bound
Estimate token count for the Backward prompt:
  dead_attempts (K=5) + Goal statement + Defs.lean + Mathlib hints

Method: run claude -p <prompt> --output-format json --debug
        parse the usage field from the response
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

FIXTURES = Path(__file__).parent
PROMPT_TEMPLATE = FIXTURES / "spike007_backward_prompt_template.md"


def run_claude_count_tokens(prompt: str) -> dict:
    """Run claude -p with the prompt and capture token usage."""

    # Write prompt to temp file to avoid shell escaping issues
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        # Use --output-format json to get structured response including usage
        cmd = ["claude", "-p", "--output-format", "json", prompt]
        print(f"Running claude -p --output-format json with {len(prompt)} chars prompt...")
        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.monotonic() - t0
        print(f"  Elapsed: {elapsed:.2f}s, rc={result.returncode}")

        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[:500]}")
            return {}

        # Try to parse JSON response (may be multiple JSON objects for stream)
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            print(f"  Could not parse JSON. Raw stdout[:500]: {result.stdout[:500] if result.stdout else '(None)'}")
            return {"raw_stdout": (result.stdout or "")[:1000]}

        usage = data.get("usage", {})
        model_usage = data.get("modelUsage", {})

        # input_tokens in usage = NEW uncached user tokens only
        # Full context = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
        new_input = usage.get("input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_create = usage.get("cache_creation_input_tokens", 0)
        total_context = new_input + cache_read + cache_create
        output_tokens = usage.get("output_tokens", 0)

        # modelUsage gives per-model breakdown (haiku for orchestration, larger model for response)
        model_totals = {}
        for model_name, mu in model_usage.items():
            model_totals[model_name] = {
                "input": mu.get("inputTokens", 0),
                "output": mu.get("outputTokens", 0),
                "cache_read": mu.get("cacheReadInputTokens", 0),
                "cache_create": mu.get("cacheCreationInputTokens", 0),
            }

        return {
            "new_input_tokens": new_input,
            "cache_read_tokens": cache_read,
            "cache_create_tokens": cache_create,
            "total_context_tokens": total_context,
            "output_tokens": output_tokens,
            "total_cost_usd": data.get("total_cost_usd"),
            "model_usage": model_totals,
            "raw_sample": result.stdout[:300],
        }
    finally:
        os.unlink(prompt_file)


def estimate_tokens_manually(text: str) -> int:
    """Rough estimate: ~4 chars per token for English/code mix."""
    return len(text) // 4


def main():
    print("spike-007: claude CLI prompt token upper bound")
    print()

    prompt_text = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    char_count = len(prompt_text)
    manual_estimate = estimate_tokens_manually(prompt_text)

    print(f"Prompt template:")
    print(f"  File: {PROMPT_TEMPLATE.name}")
    print(f"  Characters: {char_count}")
    print(f"  Manual token estimate (~4 chars/token): {manual_estimate}")
    print()

    # Simulate larger prompt variants
    # P2 Backward prompt could be larger with:
    # - More dead_attempts (K=5 already in template)
    # - Longer Defs.lean (e.g. 50 lines of Mathlib definitions)
    # - Longer parent theorem proof context

    # Variant 1: template as-is (K=5 dead attempts, simple Defs.lean)
    print("=== Variant 1: template as-is ===")
    print(f"  Chars: {char_count}, estimated tokens: {manual_estimate}")

    # Variant 2: add a 100-line Defs.lean
    defs_addition = "\n\n## Extended Defs.lean (100 lines)\n" + "\n".join(
        [f"-- def line {i}: some mathlib import or definition" for i in range(100)]
    )
    variant2 = prompt_text + defs_addition
    v2_estimate = estimate_tokens_manually(variant2)
    print(f"\n=== Variant 2: + 100-line Defs.lean ===")
    print(f"  Chars: {len(variant2)}, estimated tokens: {v2_estimate}")

    # Variant 3: longer dead_attempts (K=5 each with full error context)
    full_error_addition = "\n\n### Extended attempt error context\n" + (
        "error: unknown identifier 'foo'\n" * 50
    )
    variant3 = prompt_text + full_error_addition
    v3_estimate = estimate_tokens_manually(variant3)
    print(f"\n=== Variant 3: + extended error context ===")
    print(f"  Chars: {len(variant3)}, estimated tokens: {v3_estimate}")

    print("\n=== Running actual claude API call for token count ===")
    usage = run_claude_count_tokens(prompt_text)
    if usage and "total_context_tokens" in usage:
        print(f"  New (uncached) input tokens:  {usage['new_input_tokens']}")
        print(f"  Cache read tokens:            {usage['cache_read_tokens']}")
        print(f"  Cache creation tokens:        {usage['cache_create_tokens']}")
        print(f"  Total context (all input):    {usage['total_context_tokens']}")
        print(f"  Output tokens:                {usage['output_tokens']}")
        print(f"  Total cost USD:               {usage['total_cost_usd']}")
        print(f"  Per-model breakdown:")
        for model_name, mu in usage['model_usage'].items():
            print(f"    {model_name}: input={mu['input']}, output={mu['output']}, cache_read={mu['cache_read']}, cache_create={mu['cache_create']}")
        # For the backward prompt specifically: new_input_tokens = user message tokens
        user_msg_tokens = usage['new_input_tokens']
        print(f"\n  User message tokens (our prompt): ~{user_msg_tokens}")
        print(f"  Manual estimate (4 chars/token): {manual_estimate}")
    else:
        print(f"  Fallback to manual estimate: {manual_estimate} tokens")
        print(f"  Raw: {usage}")
        user_msg_tokens = manual_estimate

    print("\n=== Token budget analysis ===")
    context_limit_sonnet = 200_000
    context_limit_opus = 1_000_000
    prompt_tokens = user_msg_tokens if usage and "total_context_tokens" in usage else manual_estimate
    print(f"  Sonnet context limit: {context_limit_sonnet:,} tokens")
    print(f"  Opus context limit:   {context_limit_opus:,} tokens")
    print(f"  User message estimate (Backward prompt K=5): ~{prompt_tokens:,} tokens")
    # System prompt overhead (claude CLI default): typically ~500-1000 tokens
    sys_overhead = 500
    total_estimate = prompt_tokens + sys_overhead
    print(f"  + system prompt overhead (~{sys_overhead}): ~{total_estimate:,} tokens total")
    print(f"  % of sonnet context: {total_estimate/context_limit_sonnet*100:.1f}%")
    print(f"  Budget remaining (sonnet): {context_limit_sonnet - total_estimate:,} tokens")


if __name__ == "__main__":
    main()
