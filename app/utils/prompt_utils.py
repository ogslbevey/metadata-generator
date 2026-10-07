
async def get_prompt(client, phoenix_client, prompt_identifier: str, tag: str | None = None, variables: dict | None = None):
    if tag:
        prompt = await phoenix_client.prompts.get(prompt_identifier=prompt_identifier, tag=tag)
    else:
        prompt = await phoenix_client.prompts.get(prompt_identifier=prompt_identifier)
    formatted_prompt = prompt.format(variables=variables or {})
    return formatted_prompt
