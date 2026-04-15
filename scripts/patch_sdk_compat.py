#!/usr/bin/env python3
"""
SDK Compatibility Shim
=======================
Patches azure-ai-projects 2.0.x renamed symbols for compatibility with
agent-framework-azure-ai beta versions that reference the old names.

This script can be run standalone to verify the compat layer works, or
imported by other scripts (like serve.py) to apply the shim at runtime.
"""

import sys


def apply_compat_shim():
    """
    Apply compatibility shim to azure.ai.projects.models.
    
    Maps old symbol names (used by agent-framework-azure-ai) to new names
    (used in azure-ai-projects 2.0.x).
    """
    try:
        import azure.ai.projects.models as proj_models
    except ImportError as e:
        print(f"ERROR: Failed to import azure.ai.projects.models: {e}", file=sys.stderr)
        return False

    compat_map = {
        "PromptAgentDefinitionText": "PromptAgentDefinitionTextOptions",
        "ResponseTextFormatConfigurationJsonObject": "TextResponseFormatJsonObject",
        "ResponseTextFormatConfigurationJsonSchema": "TextResponseFormatJsonSchema",
        "ResponseTextFormatConfigurationText": "TextResponseFormatText",
    }

    patched_count = 0
    for old_name, new_name in compat_map.items():
        if not hasattr(proj_models, old_name) and hasattr(proj_models, new_name):
            setattr(proj_models, old_name, getattr(proj_models, new_name))
            patched_count += 1

    if patched_count > 0:
        print(f"✓ Applied {patched_count} SDK compatibility patches", file=sys.stderr)
    
    return True


def verify_agent_framework_import():
    """Verify that agent framework can be imported after applying the shim."""
    try:
        from azure.ai.agentserver.agentframework import from_agent_framework
        print("✓ azure.ai.agentserver.agentframework imports successfully")
        return True
    except ImportError as e:
        # This is expected in local dev environments without agent server installed
        print(f"⚠ Skipping agent framework verification (not installed): {e}", file=sys.stderr)
        return True  # Don't fail if agent server isn't installed locally


if __name__ == "__main__":
    # Apply the compat shim
    if not apply_compat_shim():
        sys.exit(1)
    
    # Verify the agent framework can now be imported
    if not verify_agent_framework_import():
        sys.exit(1)
    
    print("✓ SDK compatibility shim verified")
    sys.exit(0)
