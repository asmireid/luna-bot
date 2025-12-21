import os
import logging

from discord.ext.commands import Author
from openai import OpenAI
from discord.ext import commands
from utilities import *

# save chat history globally
context = list()


async def manage_context(new_context):
    global context
    context.append(new_context)
    if len(context) > Config().context_limit:
        context.pop(0)


class ChatOpenAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    # @commands.Cog.listener()
    # async def on_message(self, message):
    #     if message.author == self.bot.user:
    #         return  # ignore bot's own response

    #     if self.bot.user in message.mentions:
    #         ctx = await self.bot.get_context(message)
    #         await self.chat_openai(ctx, message=message.content)

    @commands.command(help="chats with user")
    async def chat_openai(self, ctx, *, message):
        try:
            configs = Config()

            client = OpenAI(api_key=configs.openai_api_key, base_url=configs.base_url)
            author = ctx.author.display_name
            message = f"{author}: {message}"

            print(message)

            await manage_context({'role': 'user', 'content': message})
            messages = [{'role': 'system', 'content': configs.system_prompt}]
            messages.extend(context)

            response = client.chat.completions.create(
                model=configs.model,
                messages=messages,
                max_tokens=configs.max_new_tokens,
            )

            gpt_response = response.choices[0].message.content.strip()
            await manage_context({'role': 'assistant', 'content': gpt_response})
            await try_reply(ctx, gpt_response)
        except Exception as e:
            logging.error(f"Chat Error: {repr(e)}", exc_info=True)
            await try_reply(ctx, f"Error occurred: {repr(e)}")

    @commands.command(help="displays the context")
    async def display_context(self, ctx):
        if not context:
            await try_reply(ctx, f"No context yet.")
            return

        configs = Config()

        msg_embed = make_embed(ctx, title=f"{configs.bot_name}'s Chat", descr=f"Displaying stored context.")
        for message in context:
            if message['role'] == 'user':
                msg_embed.add_field(name='user', value=message['content'], inline=False)
            elif message['role'] == 'assistant':
                msg_embed.add_field(name=configs.bot_name, value=message['content'], inline=False)
        await try_reply(ctx, msg_embed)


async def setup(bot):
    await bot.add_cog(ChatOpenAI(bot))
