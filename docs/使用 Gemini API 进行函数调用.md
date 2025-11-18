# 使用 Gemini API 进行函数调用

借助函数调用，您可以将模型连接到外部工具和 API。 模型会确定何时调用特定函数，并提供执行实际操作所需的参数，而不是生成文本回答。这使得模型能够充当自然语言与实际操作和数据之间的桥梁。函数调用有 3 个主要应用场景：

- **扩充知识**：访问数据库、API 和知识库等外部来源的信息。
- **扩展功能**：使用外部工具执行计算，并扩展模型的功能限制，例如使用计算器或创建图表。
- **执行操作**：使用 API 与外部系统互动，例如安排预约、创建账单、发送电子邮件或控制智能家居设备。

### Python

```python
from google import genai
from google.genai import types

# Define the function declaration for the model
schedule_meeting_function = {
    "name": "schedule_meeting",
    "description": "Schedules a meeting with specified attendees at a given time and date.",
    "parameters": {
        "type": "object",
        "properties": {
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of people attending the meeting.",
            },
            "date": {
                "type": "string",
                "description": "Date of the meeting (e.g., '2024-07-29')",
            },
            "time": {
                "type": "string",
                "description": "Time of the meeting (e.g., '15:00')",
            },
            "topic": {
                "type": "string",
                "description": "The subject or topic of the meeting.",
            },
        },
        "required": ["attendees", "date", "time", "topic"],
    },
}

# Configure the client and tools
client = genai.Client()
tools = types.Tool(function_declarations=[schedule_meeting_function])
config = types.GenerateContentConfig(tools=[tools])

# Send request with function declarations
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Schedule a meeting with Bob and Alice for 03/14/2025 at 10:00 AM about the Q3 planning.",
    config=config,
)

# Check for a function call
if response.candidates[0].content.parts[0].function_call:
    function_call = response.candidates[0].content.parts[0].function_call
    print(f"Function to call: {function_call.name}")
    print(f"Arguments: {function_call.args}")
    #  In a real app, you would call your function here:
    #  result = schedule_meeting(**function_call.args)
else:
    print("No function call found in the response.")
    print(response.text)
```

## 函数调用的工作原理

### 函数调用概览

函数调用涉及应用、模型和外部函数之间的结构化交互。下面详细介绍了这个流程：

1.  **定义函数声明**：在应用代码中定义函数声明。函数声明向模型描述函数的名称、参数和用途。
2.  **使用函数声明调用 LLM**：将用户提示与函数声明一起发送给模型。它会分析请求，并确定函数调用是否有帮助。如果存在，则会以结构化 JSON 对象的形式进行响应。
3.  **执行函数代码（您的责任）**：模型不会自行执行函数。应用负责处理响应并检查是否存在函数调用，如果
    - **是**：提取函数的名称和实参，并在应用中执行相应的函数。
    - **否**：模型已直接针对提示提供文本回答（此流程在示例中不太突出，但也是可能的结果）。
4.  **创建用户友好的回答**：如果执行了函数，请捕获结果，并在后续对话轮次中将其发送回模型。然后，它会使用该结果生成最终的、用户友好的回答，其中包含函数调用的信息。

此过程可以重复多次，从而实现复杂的互动和工作流程。该模型还支持在单个对话轮次中调用多个函数（并行函数调用）以及按顺序调用多个函数（组合式函数调用）。

### 第 1 步：定义函数声明

在应用代码中定义一个函数及其声明，以便用户设置光照值并发出 API 请求。此函数可以调用外部服务或 API。

#### Python

```python
# Define a function that the model can call to control smart lights
set_light_values_declaration = {
    "name": "set_light_values",
    "description": "Sets the brightness and color temperature of a light.",
    "parameters": {
        "type": "object",
        "properties": {
            "brightness": {
                "type": "integer",
                "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
            },
            "color_temp": {
                "type": "string",
                "enum": ["daylight", "cool", "warm"],
                "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
            },
        },
        "required": ["brightness", "color_temp"],
    },
}

# This is the actual function that would be called based on the model's suggestion
def set_light_values(brightness: int, color_temp: str) -> dict[str, int | str]:
    """Set the brightness and color temperature of a room light. (mock API).

    Args:
        brightness: Light level from 0 to 100. Zero is off and 100 is full brightness
        color_temp: Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.

    Returns:
        A dictionary containing the set brightness and color temperature.
    """
    return {"brightness": brightness, "colorTemperature": color_temp}
```

### 第 2 步：使用函数声明调用模型

定义函数声明后，您可以提示模型使用这些声明。它会分析提示和函数声明，并决定是直接回答还是调用函数。如果调用了函数，响应对象将包含函数调用建议。

#### Python

```python
from google.genai import types

# Configure the client and tools
client = genai.Client()
tools = types.Tool(function_declarations=[set_light_values_declaration])
config = types.GenerateContentConfig(tools=[tools])

# Define user prompt
contents = [
    types.Content(
        role="user", parts=[types.Part(text="Turn the lights down to a romantic level")]
    )
]

# Send request with function declarations
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents,
    config=config,
)

print(response.candidates[0].content.parts[0].function_call)
```

然后，模型会返回一个 `functionCall` 对象，其中包含与 OpenAPI 兼容的架构，用于指定如何调用一个或多个已声明的函数来回答用户的问题。

#### Python

```text
id=None args={'color_temp': 'warm', 'brightness': 25} name='set_light_values'
```

### 第 3 步：执行 `set_light_values` 函数代码

从模型的响应中提取函数调用详细信息，解析实参，然后执行 `set_light_values` 函数。

#### Python

```python
# Extract tool call details, it may not be in the first part.
tool_call = response.candidates[0].content.parts[0].function_call

if tool_call.name == "set_light_values":
    result = set_light_values(**tool_call.args)
    print(f"Function execution result: {result}")
```

### 第 4 步：根据函数结果创建用户友好的回答，然后再次调用模型

最后，将函数执行结果发送回模型，以便模型将此信息纳入其对用户的最终回答中。

#### Python

```python
from google import genai
from google.genai import types

# Create a function response part
function_response_part = types.Part.from_function_response(
    name=tool_call.name,
    response={"result": result},
)

# Append function call and result of the function execution to contents
contents.append(response.candidates[0].content) # Append the content from the model's response.
contents.append(types.Content(role="user", parts=[function_response_part])) # Append the function response

client = genai.Client()
final_response = client.models.generate_content(
    model="gemini-2.5-flash",
    config=config,
    contents=contents,
)

print(final_response.text)
```

至此，函数调用流程全部完成。模型成功使用 `set_light_values` 函数执行了用户的请求操作。

## 函数声明

在提示中实现函数调用时，您需要创建一个 `tools` 对象，其中包含一个或多个 `function declarations`。您可以使用 JSON（具体来说是 OpenAPI 架构格式的选定子集）来定义函数。单个函数声明可以包含以下参数：

-   `name`（字符串）：函数的唯一名称（`get_weather_forecast`、`send_email`）。请使用不含空格或特殊字符的描述性名称（使用下划线或驼峰式命名法）。
-   `description`（字符串）：对函数用途和功能的清晰而详细的说明。这对于模型了解何时使用函数至关重要。请具体说明，并在必要时提供示例（“根据位置查找影院，还可以选择查找目前正在影院上映的电影。”）。
-   `parameters`（对象）：定义函数预期的输入参数。
    -   `type`（字符串）：指定总体数据类型，例如 `object`。
    -   `properties`（对象）：列出各个参数，每个参数都包含：
        -   `type`（字符串）：参数的数据类型，例如 `string`、`integer`、`boolean`, `array`。
        -   `description`（字符串）：对参数的用途和格式的说明。提供示例和限制条件（例如，“城市和州，“加利福尼亚州旧金山”或邮政编码（例如'95616'。”）。
        -   `enum`（数组，可选）：如果参数值来自固定集，请使用“enum”列出允许的值，而不是仅在说明中描述它们。这有助于提高准确性（`"enum": ["daylight", "cool", "warm"]`）。
-   `required`（数组）：一个字符串数组，列出了函数运行所必需的参数名称。

您还可以使用 `types.FunctionDeclaration.from_callable(client=client, callable=your_function)` 直接从 Python 函数构建 `FunctionDeclarations`。

## 将函数调用与思考功能结合使用

启用“思考”功能后，模型可以在建议函数调用之前对请求进行推理，从而提高函数调用性能。Gemini API 是无状态的，在多轮对话中，模型在轮次之间的推理上下文会丢失。为了保留此上下文，您可以使用思路签名。思维签名是模型内部思维过程的加密表示形式，您可以在后续对话轮次中将其传递回模型。

多轮工具使用的标准模式是将模型完整的上一次回答附加到对话历史记录中。`content` 对象会自动包含 `thought_signatures`。如果您遵循此模式，则无需更改任何代码。

### 手动管理想法签名

如果您手动修改对话历史记录（而不是发送完整的上一个回答），并且想从思考中获益，则必须正确处理模型回合中包含的 `thought_signature`。

请遵循以下规则，确保模型的上下文得到保留：

-   始终将 `thought_signature` 发送回原始 `Part` 中的模型。
-   请勿将包含签名的 `Part` 与不包含签名的 `Part` 合并。这会打破想法的位置背景。
-   请勿合并两个都包含签名的 `Parts`，因为签名字符串无法合并。

### 检查思考签名

虽然在实现时并非必需，但您可以检查响应，以查看 `thought_signature`，用于调试或学习。

#### Python

```python
import base64
# After receiving a response from a model with thinking enabled
# response = client.models.generate_content(...)

# The signature is attached to the response part containing the function call
part = response.candidates[0].content.parts[0]
if part.thought_signature:
  print(base64.b64encode(part.thought_signature).decode("utf-8"))
```

如需详细了解思维签名的限制和使用情况，以及一般的思维模型，请参阅思维页面。

## 并行函数调用

除了单轮函数调用之外，您还可以一次调用多个函数。并行函数调用可让您同时执行多个函数，适用于函数之间没有依赖关系的情况。这在以下场景中非常有用：从多个独立来源收集数据，例如从不同数据库检索客户详细信息、检查各个仓库的库存水平，或执行多项操作，例如将公寓改造成迪斯科舞厅。

### Python

```python
power_disco_ball = {
    "name": "power_disco_ball",
    "description": "Powers the spinning disco ball.",
    "parameters": {
        "type": "object",
        "properties": {
            "power": {
                "type": "boolean",
                "description": "Whether to turn the disco ball on or off.",
            }
        },
        "required": ["power"],
    },
}

start_music = {
    "name": "start_music",
    "description": "Play some music matching the specified parameters.",
    "parameters": {
        "type": "object",
        "properties": {
            "energetic": {
                "type": "boolean",
                "description": "Whether the music is energetic or not.",
            },
            "loud": {
                "type": "boolean",
                "description": "Whether the music is loud or not.",
            },
        },
        "required": ["energetic", "loud"],
    },
}

dim_lights = {
    "name": "dim_lights",
    "description": "Dim the lights.",
    "parameters": {
        "type": "object",
        "properties": {
            "brightness": {
                "type": "number",
                "description": "The brightness of the lights, 0.0 is off, 1.0 is full.",
            }
        },
        "required": ["brightness"],
    },
}
```

配置函数调用模式，以允许使用所有指定的工具。 如需了解详情，您可以参阅配置函数调用。

### Python

```python
from google import genai
from google.genai import types

# Configure the client and tools
client = genai.Client()
house_tools = [
    types.Tool(function_declarations=[power_disco_ball, start_music, dim_lights])
]
config = types.GenerateContentConfig(
    tools=house_tools,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        disable=True
    ),
    # Force the model to call 'any' function, instead of chatting.
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode='ANY')
    ),
)

chat = client.chats.create(model="gemini-2.5-flash", config=config)
response = chat.send_message("Turn this place into a party!")

# Print out each of the function calls requested from this single call
print("Example 1: Forced function calling")
for fn in response.function_calls:
    args = ", ".join(f"{key}={val}" for key, val in fn.args.items())
    print(f"{fn.name}({args})")
```

每个打印结果都反映了模型请求的单个函数调用。如需将结果发送回去，请按请求顺序包含响应。

Python SDK 支持自动函数调用，可自动将 Python 函数转换为声明，并为您处理函数调用执行和响应周期。以下是 disco 用例的示例。

**注意**： 自动函数调用目前仅为 Python SDK 功能。

### Python

```python
from google import genai
from google.genai import types

# Actual function implementations
def power_disco_ball_impl(power: bool) -> dict:
    """Powers the spinning disco ball.

    Args:
        power: Whether to turn the disco ball on or off.

    Returns:
        A status dictionary indicating the current state.
    """
    return {"status": f"Disco ball powered {'on' if power else 'off'}"}

def start_music_impl(energetic: bool, loud: bool) -> dict:
    """Play some music matching the specified parameters.

    Args:
        energetic: Whether the music is energetic or not.
        loud: Whether the music is loud or not.

    Returns:
        A dictionary containing the music settings.
    """
    music_type = "energetic" if energetic else "chill"
    volume = "loud" if loud else "quiet"
    return {"music_type": music_type, "volume": volume}

def dim_lights_impl(brightness: float) -> dict:
    """Dim the lights.

    Args:
        brightness: The brightness of the lights, 0.0 is off, 1.0 is full.

    Returns:
        A dictionary containing the new brightness setting.
    """
    return {"brightness": brightness}

# Configure the client
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[power_disco_ball_impl, start_music_impl, dim_lights_impl]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Do everything you need to this place into party!",
    config=config,
)

print("\nExample 2: Automatic function calling")
print(response.text)
# I've turned on the disco ball, started playing loud and energetic music, and dimmed the lights to 50% brightness. Let's get this party started!```

## 组合式函数调用

组合式或顺序式函数调用可让 Gemini 将多个函数调用链接在一起，以满足复杂的请求。例如，为了回答“获取我当前位置的温度”，Gemini API 可能会先调用 `get_current_location()` 函数，然后再调用以位置为参数的 `get_weather()` 函数。

以下示例演示了如何使用 Python SDK 和自动函数调用来实现组合式函数调用。

### Python

此示例使用 `google-genai` Python SDK 的自动函数调用功能。SDK 会自动将 Python 函数转换为所需的架构，在模型请求时执行函数调用，并将结果发送回模型以完成任务。

```python
import os
from google import genai
from google.genai import types

# Example Functions
def get_weather_forecast(location: str) -> dict:
    """Gets the current weather temperature for a given location."""
    print(f"Tool Call: get_weather_forecast(location={location})")
    # TODO: Make API call
    print("Tool Response: {'temperature': 25, 'unit': 'celsius'}")
    return {"temperature": 25, "unit": "celsius"}  # Dummy response

def set_thermostat_temperature(temperature: int) -> dict:
    """Sets the thermostat to a desired temperature."""
    print(f"Tool Call: set_thermostat_temperature(temperature={temperature})")
    # TODO: Interact with a thermostat API
    print("Tool Response: {'status': 'success'}")
    return {"status": "success"}

# Configure the client and model
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[get_weather_forecast, set_thermostat_temperature]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
    config=config,
)

# Print the final, user-facing response
print(response.text)
```

### 预期输出

运行代码时，您会看到 SDK 编排函数调用。模型首先调用 `get_weather_forecast`，接收温度，然后根据提示中的逻辑调用 `set_thermostat_temperature` 并传入正确的值。

```text
Tool Call: get_weather_forecast(location=London)
Tool Response: {'temperature': 25, 'unit': 'celsius'}
Tool Call: set_thermostat_temperature(temperature=20)
Tool Response: {'status': 'success'}
OK. I've set the thermostat to 20°C.
```

组合式函数调用是一项原生 Live API 功能。这意味着 Live API 可以像 Python SDK 一样处理函数调用。

### Python

```python
# Light control schemas
turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}

prompt = """
  Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
  """

tools = [
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
]

await run(prompt, tools=tools, modality="AUDIO")
```

## 函数调用模式

通过 Gemini API，您可以控制模型使用所提供工具（函数声明）的方式。具体来说，您可以在 `.function_calling_config` 中设置模式。

-   **AUTO (Default)**：模型会根据提示和上下文决定是生成自然语言回答还是建议函数调用。这是最灵活的模式，建议在大多数情况下使用。
-   **ANY**：模型会受到限制，始终预测函数调用，并保证遵循函数架构。如果未指定 `allowed_function_names`，模型可以从提供的任何函数声明中进行选择。如果 `allowed_function_names` 以列表形式提供，模型只能从该列表中的函数中进行选择。如果您需要针对每个提示（如果适用）获得函数调用响应，请使用此模式。
-   **NONE**：模型禁止进行函数调用。这相当于发送不含任何函数声明的请求。使用此参数可暂时停用函数调用，而无需移除工具定义。

### Python

```python
from google.genai import types

# Configure function calling mode
tool_config = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(
        mode="ANY", allowed_function_names=["get_current_temperature"]
    )
)

# Create the generation config
config = types.GenerateContentConfig(
    tools=[tools],  # not defined here.
    tool_config=tool_config,
)
```

## 自动函数调用（仅限 Python）

使用 Python SDK 时，您可以直接将 Python 函数作为工具提供。SDK 会将这些函数转换为声明，管理函数调用执行，并为您处理响应周期。使用类型提示和文档字符串定义函数。为获得最佳效果，建议使用 Google 风格的文档字符串。 然后，SDK 将自动执行以下操作：

1.  检测模型返回的函数调用响应。
2.  在代码中调用相应的 Python 函数。
3.  将函数的响应发送回模型。
4.  返回模型的最终文本回答。

SDK 目前不会将实参说明解析到生成的函数声明的属性说明槽中。而是将整个文档字符串作为顶级函数说明发送。

### Python

```python
from google import genai
from google.genai import types

# Define the function with type hints and docstring
def get_current_temperature(location: str) -> dict:
    """Gets the current temperature for a given location.

    Args:
        location: The city and state, e.g. San Francisco, CA

    Returns:
        A dictionary containing the temperature and unit.
    """
    # ... (implementation) ...
    return {"temperature": 25, "unit": "Celsius"}

# Configure the client
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[get_current_temperature]
)  # Pass the function itself

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="What's the temperature in Boston?",
    config=config,
)

print(response.text)  # The SDK handles the function call and returns the final text
```

您可以使用以下方法停用自动函数调用：

### Python

```python
config = types.GenerateContentConfig(
    tools=[get_current_temperature],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)
```

### 自动函数架构声明

该 API 能够描述以下任何类型。允许使用 Pydantic 类型，前提是这些类型上定义的字段也由允许的类型组成。此处不太支持字典类型（如 `dict[str: int]`），请勿使用。

#### Python

```python
AllowedType = (
  int | float | bool | str | list['AllowedType'] | pydantic.BaseModel)
```

如需查看推断架构的实际效果，您可以使用 `from_callable` 对其进行转换：

#### Python

```python
from google import genai
from google.genai import types

def multiply(a: float, b: float):
    """Returns a * b."""
    return a * b

client = genai.Client()
fn_decl = types.FunctionDeclaration.from_callable(callable=multiply, client=client)

# to_json_dict() provides a clean JSON representation.
print(fn_decl.to_json_dict())
```

## 多工具使用：将原生工具与函数调用相结合

您可以同时启用多个工具，将原生工具与函数调用相结合。以下示例展示了如何使用 Live API 在请求中启用两项工具：Google 搜索基础和代码执行。

**注意**： 目前，多工具使用仅为 Live API 功能。为简洁起见，此处省略了处理异步 WebSocket 设置的 `run()` 函数声明。

### Python

```python
# Multiple tasks example - combining lights, code execution, and search
prompt = """
  Hey, I need you to do three things for me.

    1.  Turn on the lights.
    2.  Then compute the largest prime palindrome under 100000.
    3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

  Thanks!
  """

tools = [
    {'google_search': {}},
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]} # not defined here.
]

# Execute the prompt with specified tools in audio modality
await run(prompt, tools=tools, modality="AUDIO")
```

Python 开发者可以在 Live API Tool Use 笔记本中试用此功能。

## 模型上下文协议 (MCP)

Model Context Protocol (MCP) 是一种开放标准，用于将 AI 应用与外部工具和数据相连接。 MCP 提供了一种通用协议，供模型访问上下文，例如函数（工具）、数据源（资源）或预定义的提示。

Gemini SDK 内置了对 MCP 的支持，可减少样板代码并为 MCP 工具提供自动工具调用。当模型生成 MCP 工具调用时，Python 和 JavaScript 客户端 SDK 可以自动执行 MCP 工具，并在后续请求中将响应发送回模型，从而继续此循环，直到模型不再进行任何工具调用。

在此处，您可以找到一个示例，了解如何将本地 MCP 服务器与 Gemini 和 `mcp` SDK 搭配使用。

### Python

确保在您选择的平台上安装了最新版本的 `mcp` SDK。

```bash
pip install mcp
```

**注意**： Python 支持通过将 `ClientSession` 传递到 `tools` 参数中来实现自动工具调用。如果您想停用它，可以提供已停用的 `True` 的 `automatic_function_calling`。

```python
import os
import asyncio
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai

client = genai.Client()

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="npx",  # Executable
    args=["-y", "@philschmid/weather-mcp"],  # MCP Server
    env=None,  # Optional environment variables
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Prompt to get the weather for the current day in London.
            prompt = f"What is the weather in London in {datetime.now().strftime('%Y-%m-%d')}?"

            # Initialize the connection between client and server
            await session.initialize()

            # Send request to the model with MCP function declarations
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[session],  # uses the session, will automatically call the tool
                    # Uncomment if you **don't** want the SDK to automatically call the tool
                    # automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(
                    #     disable=True
                    # ),
                ),
            )
            print(response.text)

# Start the asyncio event loop and run the main function
asyncio.run(run())
```

### 内置 MCP 支持的限制

内置 MCP 支持是我们 SDK 中的一项实验性功能，具有以下限制：

-   仅支持工具，不支持资源或提示
-   适用于 Python 和 JavaScript/TypeScript SDK。
-   未来版本可能会出现重大变更。

如果这些限制影响了您构建的内容，您可以随时选择手动集成 MCP 服务器。

## 支持的模型

本部分列出了模型及其函数调用功能。不包括实验性模型。您可以在模型概览页面上找到全面的功能概览。

| 型号                  | 函数调用 | 并行函数调用 | 组合式函数调用 |
| --------------------- | -------- | ------------ | -------------- |
| Gemini 2.5 Pro        | ✔️       | ✔️           | ✔️             |
| Gemini 2.5 Flash      | ✔️       | ✔️           | ✔️             |
| Gemini 2.5 Flash-Lite | ✔️       | ✔️           | ✔️             |
| Gemini 2.0 Flash      | ✔️       | ✔️           | ✔️             |
| Gemini 2.0 Flash-Lite | X        | X            | X              |

## 最佳做法

-   **函数和参数说明**：说明应极其清晰且具体。模型会根据这些信息选择正确的函数并提供适当的实参。
-   **命名**：使用描述性函数名称（不含空格、英文句点或短划线）。
-   **强类型**：为参数使用特定类型（整数、字符串、枚举），以减少错误。如果某个形参的有效值集有限，请使用枚举。
-   **工具选择**：虽然模型可以使用任意数量的工具，但提供的工具过多可能会增加选择错误或次优工具的风险。为获得最佳效果，请尽量仅提供与上下文或任务相关的工具，最好将有效工具集保持在 10-20 个以内。如果您有大量工具，请考虑根据对话上下文动态选择工具。
-   **提示工程**：
    -   提供背景信息：告知模型其角色（例如，“你是一位乐于助人的天气助理。”）。
    -   提供指令：指定如何以及何时使用函数（例如，“不要猜测日期；预测时始终使用未来的日期。”）。
    -   鼓励澄清：指示模型在需要时提出澄清性问题。
-   **温度**：使用较低的温度（例如 0），以实现更具确定性和可靠性的函数调用。
-   **验证**：如果函数调用会产生重大后果（例如下单），请在执行之前先向用户验证该调用。
-   **错误处理**：在函数中实现强大的错误处理机制，以妥善处理意外输入或 API 故障。返回信息丰富的错误消息，供模型用来生成对用户的实用回答。
-   **安全性**：调用外部 API 时，请务必注意安全性。使用适当的身份验证和授权机制。避免在函数调用中公开敏感数据。
-   **token 限制**：函数说明和参数会计入输入 token 限制。如果您遇到 token 限制，请考虑限制函数数量或说明长度，将复杂的任务分解为更小、更集中的函数集。