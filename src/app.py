from __future__ import annotations as _annotations
import os
import time
import logging
import asyncio
import random
import chainlit as cl
from dotenv import load_dotenv
from pydantic import BaseModel

from openai import AzureOpenAI

from pydantic import BaseModel
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai.types.responses import ResponseTextDeltaEvent
from openai import AsyncAzureOpenAI
from azure.ai.agents.models import (
    AgentStreamEvent,
    MessageDeltaChunk,
    MessageRole,
    ThreadRun,
    MessageTextContent
)
from agents import (
    Agent,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    function_tool,
    handoff,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
    set_default_openai_client,
    set_default_openai_api,
    add_trace_processor
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.tracing.processors import ConsoleSpanExporter, BatchTraceProcessor

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel

load_dotenv()
# Disable verbose connection logs
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.WARNING)
# set_tracing_disabled(True)

console_exporter = ConsoleSpanExporter()
console_processor = BatchTraceProcessor(exporter=console_exporter)
add_trace_processor(console_processor)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY= os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME_REASONING = 'o4-mini'
DEPLOYMENT_NAME = "gpt-4.1"
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION") # this might change in the future

project_endpoint = os.getenv("PROJECT_ENDPOINT")
GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID = os.getenv("GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID") # Azure AI Foundry Agent ID

azure_client = AsyncAzureOpenAI(
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
)

set_default_openai_client(azure_client, use_for_tracing=False)
set_default_openai_api("chat_completions")

project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),  # Use Azure Default Credential for authentication
)


### TOOLS
@function_tool(
    name_override="gender_discriminatory_knowledge_tool", description_override="Lookup document regarding the gender discriminatory or search latest information from web."
)
async def gender_discriminatory_knowledge_tool(question: str) -> str:
    print(f"User Question: {question}")
    start_time = cl.user_session.get("start_time")
    print(f"Elapsed time: {(time.time() - start_time):.2f} seconds - gender_discriminatory_knowledge_tool")
    is_first_token = None

    try:
        # create thread for the agent
        thread_id = cl.user_session.get("new_threads").get(GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID)
        print(f"thread ID: {thread_id}")

        # Create a message, with the prompt being the message content that is sent to the model
        project_client.agents.messages.create(
            thread_id=thread_id,
            role="user",
            content=question,
        )
        

        async with cl.Step(name="gender_discriminatory_knowledge_tool") as step:
            step.input = question

            # Run the agent to process tne message in the thread
            with project_client.agents.runs.stream(thread_id=thread_id, agent_id=GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID) as stream:
                for event_type, event_data, _ in stream:
                    if isinstance(event_data, MessageDeltaChunk):
                        # Stream the message delta chunk
                        await step.stream_token(event_data.text)
                        if not is_first_token:
                            print(f"Elapsed time: {(time.time() - start_time):.2f} seconds - {event_data.text}")
                            is_first_token = True

                    elif isinstance(event_data, ThreadRun):
                        if event_data.status == "failed":
                            print(f"Run failed. Error: {event_data.last_error}")
                            raise Exception(event_data.last_error)

                    elif event_type == AgentStreamEvent.ERROR:
                        print(f"An error occurred. Data: {event_data}")
                        raise Exception(event_data)

        # Get all messages from the thread
        messages = project_client.agents.messages.list(thread_id)
        
        for msg in messages:
            last_part = msg.content[-1]
            if isinstance(last_part, MessageTextContent):
                print(f"{msg.role}: {last_part.text.value}")
                return last_part.text.value
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return "I'm sorry, I encountered an error while processing your request. Please try again."



@function_tool
async def check_dating_scam_recruitment_tool(
    question: str
) -> str:
    """
    Check if the user input that is job description contains any dating scam recruitment.
    Args:
        question: The user input that is job description.
    """
    developer_message = """
    あなたは出会い系の利用を目的としたサクラ募集の求人情報を検出するためのコンプライアンスチェッカーAIです。
    求人情報はコンプライアンスチェックをすり抜けるように、直接的な表現を避けて記載されていることが多いため、非常に注意深く疑い深くチェックしてください。

    求人情報：
    """

    class ComplianceItemResult(BaseModel):
        status: Literal["OK", "Suspicious", "NG", "Exception"]
        reaosnon_details: str
        match_details: str


    client = AzureOpenAI(
		azure_endpoint = AZURE_OPENAI_ENDPOINT, 
		api_key=AZURE_OPENAI_API_KEY,  
		api_version=AZURE_OPENAI_API_VERSION,
		)

    completion_reasoning = client.beta.chat.completions.parse(
		model=DEPLOYMENT_NAME_REASONING, # replace with the model deployment name of your reasoning deployment
		messages=[
			{"role": "developer", "content": developer_message},
			{"role": "user", "content": question},
		],
		# response_formast=ComplianceItemResult,
		reasoning_effort = "high"
	)
    
    completion = client.beta.chat.completions.parse(
		model=DEPLOYMENT_NAME, # replace with the model deployment name of your gpt deployment
		messages=[
			{"role": "system", "content": "求人情報のコンプライアンスチェック結果を構造化して出力します。"},
			{"role": "user", "content": completion_reasoning.choices[0].message.content},
		],
		response_format=ComplianceItemResult,
	)
    
    return completion.choices[0].message.parsed


@function_tool
async def check_gender_discriminatory_tool(
    question: str
) -> str:
    """
    
    """
    developer_message = """
    あなたは、求人票の表現が「男女雇用機会均等法 第5条」に違反していないかを確認する専門のコンプライアンスチェックAIです。
	以下のすべての項目をチェックして、すべての結果と判断した理由を出力してください。

	1. **gender_ratio_stated（募集人数の性別比率の記載）**  
	　例：`募集人数：男性5人、女性1人` → NG

	2. **gender_condition_differs（性別ごとに条件が異なる）**  
	　例：`営業スタッフ（男性：経験者、女性：未経験可）` → NG

	3. **gendered_job_titles（性別を指す用語を職種・応募条件として使用）**  
	　例：`営業マン募集`, `看護婦だった方歓迎`, `カメラマン（女性）`など → NG  
	　例外：`元看護婦も活躍中`, `サラリーマンに人気の〜`などはOK

	4. **explicit_gender_limitation（明確に性別を制限している）**  
	　例：`女性のみ`, `男性限定`, `女性専用フィットネスの受付（女性のみ）` → NG  
	　例外：以下のような正当な理由がある場合はOK（Exception）  
	　・宗教的・芸能的・業務上の性質による性別要件（巫女、女優など）  
	　・防犯上の理由（夜間警備員など）  
	　・風紀上の理由（女性トイレの清掃など）

	5. **effectively_gender_limited（実質的に性別を制限している表現）**  
	　例：`女性優先`, `男性限定のキャリア形成`, `女性向きの職場`など → NG または Suspicious  
	　※ `女性活躍中`, `主婦歓迎`, `女性の多い職場` など事実記載や歓迎表現はOK

	求人情報：
    """

    class ComplianceItemResult(BaseModel):
        status: Literal["OK", "Suspicious", "NG", "Exception"]
        reaosnon_details: str
        match_details: str


    client = AzureOpenAI(
		azure_endpoint = AZURE_OPENAI_ENDPOINT, 
		api_key=AZURE_OPENAI_API_KEY,  
		api_version=AZURE_OPENAI_API_VERSION,
		)

    completion_reasoning = client.beta.chat.completions.parse(
		model=DEPLOYMENT_NAME_REASONING, # replace with the model deployment name of your reasoning deployment
		messages=[
			{"role": "developer", "content": developer_message},
			{"role": "user", "content": question},
		],
		# response_formast=ComplianceItemResult,
		reasoning_effort = "high"
	)
    
    completion = client.beta.chat.completions.parse(
		model=DEPLOYMENT_NAME, # replace with the model deployment name of your gpt deployment
		messages=[
			{"role": "system", "content": "求人情報のコンプライアンスチェック結果を構造化して出力します。"},
			{"role": "user", "content": completion_reasoning.choices[0].message.content},
		],
		response_format=ComplianceItemResult,
	)
    
    return completion.choices[0].message.parsed


@function_tool
async def correction_tool(
	check_result: str
) -> str:
	"""
	Review and correct the compliance check results from other agents.
	Args:
		check_result: The compliance check result that needs review and correction.
	"""
	developer_message = """
	あなたは他のエージェントによるチェック結果でコンプライアンス違反が発生していた場合に、その内容をどのように是正すべきかを提案するエキスパートです。
	コンプライアンスチェック結果は、他のエージェントによって出力されたものであり、あなたはその内容をレビューし、必要に応じて是正する役割を担っています。
	是正結果は元のフォーマットを維持しつつ、よりコンプライアンス違反をどのように解決できるかを提示してください。
	"""

	client = AzureOpenAI(
		azure_endpoint = AZURE_OPENAI_ENDPOINT, 
		api_key=AZURE_OPENAI_API_KEY,  
		api_version=AZURE_OPENAI_API_VERSION,
	)

	completion_reasoning = client.beta.chat.completions.parse(
		model=DEPLOYMENT_NAME_REASONING,
		messages=[
			{"role": "developer", "content": developer_message},
			{"role": "user", "content": check_result},
		],
		reasoning_effort = "high"
	)
 
	return completion_reasoning.choices[0].message.content


### AGENTS
check_dating_scam_agent = Agent(
    name="check_dating_scam_agent",
    handoff_description="Checking if the user input that is job description contains any dating scam recruitment.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are a compliance checker AI designed to detect job listings recruiting "Sakura" for the purpose of using dating services.
    Since these listings often avoid direct expressions to bypass compliance checks, you must review them with utmost caution and skepticism.
    You must answer the question in Japanese.
    
    # Routine
    1. Identify the last question asked by the customer.
    2. Use the dating scam recruitment tool to check if job description contains any dating scam recruitment. Do not rely on your own knowledge.
    3. Provide a detailed assessment of any violations found.
	4. Ensure that the response includes the full output from the recruitment tool as a citation in the answer.
    5. If you cannot answer the question, transfer back to the triage agent.""",
    tools=[check_dating_scam_recruitment_tool],
    model=OpenAIChatCompletionsModel(
        model=DEPLOYMENT_NAME,
        openai_client=azure_client,
    ),
)

check_gender_discriminatory_agent = Agent(
    name="check_gender_discriminatory_agent",
	handoff_description="Checking if job descriptions contain gender discriminatory expressions violating equal employment laws.",
	instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
	You are a compliance checker AI specialized in detecting gender discriminatory expressions in job listings that violate the Equal Employment Opportunity Act Article 5.
	You analyze job postings to identify potential gender discrimination issues.
 	You must answer the question in Japanese.
	
	# Routine
	1. Identify the job description provided by the customer.
	2. Use the `check_gender_discriminatory_tool` to analyze the content for gender discriminatory expressions. Do not rely on your own knowledge.
	3. Provide a detailed assessment of any violations found.
	4. Ensure that the response includes the full output from the recruitment tool as a citation in the answer.
	5. If you asked about `equal employment laws`, you should use `gender_discriminatory_knowledge_tool` to search for the context.
	6. If you cannot properly analyze the description, transfer back to the triage agent.""",
	tools=[check_gender_discriminatory_tool, gender_discriminatory_knowledge_tool],
	model=OpenAIChatCompletionsModel(
		model=DEPLOYMENT_NAME,
		openai_client=azure_client,
	),
)

correction_agent = Agent(
	name="Correction Agent",
	handoff_description="An agent specialized in reviewing and correcting compliance check results from other agents.",
	instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
	You are a compliance correction agent. You review and improve the results from other compliance checking agents.
	You must answer the question in Japanese.
	
	# Routine
	1. Review the compliance check result provided by the user.
	2. Analyze the check result and provide corrections.
	3. Present the corrected assessment with clear explanations of what was improved.
	4. If you cannot correct the result, transfer back to the triage agent.""",
	# tools=[correction_tool],
	model=OpenAIChatCompletionsModel(
		model=DEPLOYMENT_NAME,
		openai_client=azure_client,
	),
)

triage_agent = Agent(
    name="Triage Agent",
    handoff_description="A triage agent that can delegate a customer's request to the appropriate agent.",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX} "
        "You are a helpful triaging agent. You can use your tools to delegate questions to other appropriate agents."
        "Use the response from other agents to answer the question. Do not rely on your own knowledge."
        "Other than greetings, do not answer any questions yourself."
        "If a user explicitly asks for a human agent or live support, transfer them to the Live Agent."
        "If a user is asking the same question more than two times, transfer them to the Live Agent."
        "# Very Important Notes"
        "- Never respond to the user with any PII data such as password, ID number, etc."
    ),
    handoffs=[
        correction_agent,
        check_dating_scam_agent,
        check_gender_discriminatory_agent
    ],
    model=OpenAIChatCompletionsModel(
        model=DEPLOYMENT_NAME,
        openai_client=azure_client,
    ),
)

check_dating_scam_agent.handoffs.append(triage_agent)
correction_agent.handoffs.append(triage_agent)
check_gender_discriminatory_agent.handoffs.append(triage_agent)

### Main logic
async def main(user_input: str) -> None:
    current_agent = cl.user_session.get("current_agent")
    input_items = cl.user_session.get("input_items")
    print(f"Received message: {user_input}")

    # Show thinking message to user
    msg = await cl.Message(f"thinking...", author="agent").send()
    msg_final = cl.Message("", author="agent")

    # Set an empty list for delete_threads in the user session
    cl.user_session.set("delete_threads", [])
    is_thinking = True

    try:
        input_items.append({"content": user_input, "role": "user"})
        # Run the agent with streaming
        result = Runner.run_streamed(current_agent, input_items)
        last_agent = ""

        # Stream the response
        async for event in result.stream_events():
            # Get the last agent name
            if event.type == "agent_updated_stream_event":
                if is_thinking:
                    last_agent = event.new_agent.name
                    msg.content = f"[{last_agent}] thinking..."
                    await msg.send()
            # Get the message delta chunk
            elif event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                if is_thinking:
                    is_thinking = False
                    await msg.remove()
                    msg_final.content = f"[{last_agent}] "
                    await msg_final.send()

                await msg_final.stream_token(event.data.delta)

        # Update the current agent and input items in the user session
        cl.user_session.set("current_agent", result.last_agent)
        cl.user_session.set("input_items", result.to_input_list())

    except Exception as e:
        logger.error(f"Error: {e}")
        msg_final.content = "I'm sorry, I encountered an error while processing your request. Please try again."

    # show the last response in the UI
    await msg_final.update()


# Chainlit setup
@cl.on_chat_start
async def on_chat_start():
    # Initialize user session
    current_agent: Agent = triage_agent
    input_items: list[TResponseInputItem] = []

    cl.user_session.set("current_agent", current_agent)
    cl.user_session.set("input_items", input_items)

    # Create a thread for the agent
    thread_gender = project_client.agents.threads.create()
    cl.user_session.set("new_threads", {
        GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID: thread_gender.id,
    })


@cl.on_message
async def on_message(message: cl.Message):
    cl.user_session.set("start_time", time.time())
    user_input = message.content

    for element in message.elements:
        # check if the element is an image
        if element.mime.startswith("image/"):
            user_input += f"\n[uploaded image] {element.path}"
            print(f"Received file: {element.path}")

    asyncio.run(main(user_input))

if __name__ == "__main__":
    # Chainlit will automatically run the application
    pass