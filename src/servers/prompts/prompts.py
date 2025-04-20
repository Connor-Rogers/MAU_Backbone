class Prompts:
    def __init__(self):
        self.prompts = {
            "greeting": "Hello! How can I assist you today?",
            "farewell": "Goodbye! Have a great day!",
            "help": "Here are some commands you can use: ..."
        }

    def get_prompt(self, key):
        return self.prompts.get(key, "Prompt not found.")
    