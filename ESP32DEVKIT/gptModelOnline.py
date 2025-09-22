import g4f
def gpt4_ask(prompt):
    response = g4f.ChatCompletion.create(
        model="gpt-4",
        provider=g4f.Provider.AnyProvider,
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=False,
        max_tokens=128
    )
    return response


