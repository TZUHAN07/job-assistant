import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

def get_job_requirements():
    return {
        "job_title": "軟體助理工程師",
        "requirements": [
            "使用 Node.js 開發後端 API",
            "操作 MongoDB 資料庫",
            "使用 Socket.IO 實作即時聊天",
        ]
    }


job_tool_declaration = {
    "name": "get_job_requirements",
    "description": (
        "取得目前練習職缺的職稱與技能需求。"
        "需要根據職缺準備面試題時使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

if __name__ == "__main__":
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("請先在 .env 設定 Gemini API key")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000),
    )

    tool = types.Tool(
        function_declarations=[job_tool_declaration]
    )

    prompt = "請先查詢目前練習職缺的需求，再用繁體中文幫我準備一道面試題。"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[tool],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )

    if response.function_calls:
        tool_results = []

        for call in response.function_calls:
            print("模型要求的工具：", call.name)
            print("模型提供的參數：", call.args)

            if call.name != "get_job_requirements":
                result = {"error": "不支援這個工具"}
            elif call.args:
                result = {"error": "這個工具不接受參數"}
            else:
                result = get_job_requirements()

            print("工具執行結果：")
            print(result)

            tool_results.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id,
                        name=call.name,
                        response=result,
                    )
                )
            )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
            response.candidates[0].content,
            types.Content(
                role="user",
                parts=tool_results,
            ),
        ]

        final_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[tool],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="NONE"
                    )
                ),
            ),
        )

        print("Gemini 產生的面試題：")
        print(final_response.text or "這次沒有取得文字回覆。")
    else:
        print("這次模型沒有提出工具請求。")
        print(response.text or "這次沒有取得文字回覆。")