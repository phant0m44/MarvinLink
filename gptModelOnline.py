import g4f

def gpt4(prompt):
    response = g4f.ChatCompletion.create(
        model="gpt-4",
        provider=g4f.Provider.You,
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=False,
        max_tokens=150
    )
    return response

print(gpt4("привіт, яка зараз температура?[temp_kitchen: 23; temp_bathroom: 19; temp_outside: 12; localtime: 20:02;]"))
