from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import httpx

from agno.exceptions import ModelProviderError
from agno.media import Audio
from agno.models.base import Model
from agno.models.message import Message
from agno.models.response import ModelResponse
from agno.utils.log import logger
from agno.utils.openai import images_to_message

try:
    from groq import APIError, APIResponseValidationError, APIStatusError
    from groq import AsyncGroq as AsyncGroqClient
    from groq import Groq as GroqClient
    from groq.types.audio import Transcription
    from groq.types.chat import ChatCompletion
    from groq.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta, ChoiceDeltaToolCall
except (ModuleNotFoundError, ImportError):
    raise ImportError("`groq` not installed. Please install using `pip install groq`")


@dataclass
class Groq(Model):
    """
    A class for interacting with Groq models.

    For more information, see: https://console.groq.com/docs/libraries
    """

    id: str = "llama-3.3-70b-versatile"
    name: str = "Groq"
    provider: str = "Groq"

    # Request parameters
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Any] = None
    logprobs: Optional[bool] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    temperature: Optional[float] = None
    top_logprobs: Optional[int] = None
    top_p: Optional[float] = None
    user: Optional[str] = None
    extra_headers: Optional[Any] = None
    extra_query: Optional[Any] = None
    request_params: Optional[Dict[str, Any]] = None

    # Client parameters
    api_key: Optional[str] = None
    base_url: Optional[Union[str, httpx.URL]] = None
    timeout: Optional[int] = None
    max_retries: Optional[int] = None
    default_headers: Optional[Any] = None
    default_query: Optional[Any] = None
    http_client: Optional[httpx.Client] = None
    client_params: Optional[Dict[str, Any]] = None

    # Groq clients
    client: Optional[GroqClient] = None
    async_client: Optional[AsyncGroqClient] = None

    def _get_client_params(self) -> Dict[str, Any]:
        # Fetch API key from env if not already set
        if not self.api_key:
            self.api_key = getenv("GROQ_API_KEY")
            if not self.api_key:
                logger.error("GROQ_API_KEY not set. Please set the GROQ_API_KEY environment variable.")

        # Define base client params
        base_params = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }
        # Create client_params dict with non-None values
        client_params = {k: v for k, v in base_params.items() if v is not None}
        # Add additional client params if provided
        if self.client_params:
            client_params.update(self.client_params)
        return client_params

    def get_client(self) -> GroqClient:
        """
        Returns a Groq client.

        Returns:
            GroqClient: An instance of the Groq client.
        """
        if self.client:
            return self.client

        client_params: Dict[str, Any] = self._get_client_params()
        if self.http_client is not None:
            client_params["http_client"] = self.http_client

        self.client = GroqClient(**client_params)
        return self.client

    def get_async_client(self) -> AsyncGroqClient:
        """
        Returns an asynchronous Groq client.

        Returns:
            AsyncGroqClient: An instance of the asynchronous Groq client.
        """
        if self.async_client:
            return self.async_client

        client_params: Dict[str, Any] = self._get_client_params()
        if self.http_client:
            client_params["http_client"] = self.http_client
        else:
            # Create a new async HTTP client with custom limits
            client_params["http_client"] = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100)
            )
        return AsyncGroqClient(**client_params)

    @property
    def request_kwargs(self) -> Dict[str, Any]:
        """
        Returns keyword arguments for API requests.

        Returns:
            Dict[str, Any]: A dictionary of keyword arguments for API requests.
        """
        # Define base request parameters
        base_params = {
            "frequency_penalty": self.frequency_penalty,
            "logit_bias": self.logit_bias,
            "logprobs": self.logprobs,
            "max_tokens": self.max_tokens,
            "presence_penalty": self.presence_penalty,
            "response_format": self.response_format,
            "seed": self.seed,
            "stop": self.stop,
            "temperature": self.temperature,
            "top_logprobs": self.top_logprobs,
            "top_p": self.top_p,
            "user": self.user,
            "extra_headers": self.extra_headers,
            "extra_query": self.extra_query,
        }
        # Filter out None values
        request_params = {k: v for k, v in base_params.items() if v is not None}
        # Add tools
        if self._tools is not None:
            request_params["tools"] = self._tools
            if self.tool_choice is not None:
                request_params["tool_choice"] = self.tool_choice
        # Add additional request params if provided
        if self.request_params:
            request_params.update(self.request_params)
        return request_params

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.

        Returns:
            Dict[str, Any]: The dictionary representation of the model.
        """
        model_dict = super().to_dict()
        model_dict.update(
            {
                "frequency_penalty": self.frequency_penalty,
                "logit_bias": self.logit_bias,
                "logprobs": self.logprobs,
                "max_tokens": self.max_tokens,
                "presence_penalty": self.presence_penalty,
                "response_format": self.response_format,
                "seed": self.seed,
                "stop": self.stop,
                "temperature": self.temperature,
                "top_logprobs": self.top_logprobs,
                "top_p": self.top_p,
                "user": self.user,
                "extra_headers": self.extra_headers,
                "extra_query": self.extra_query,
            }
        )
        if self._tools is not None:
            model_dict["tools"] = self._tools
            if self.tool_choice is not None:
                model_dict["tool_choice"] = self.tool_choice
            else:
                model_dict["tool_choice"] = "auto"
        cleaned_dict = {k: v for k, v in model_dict.items() if v is not None}
        return cleaned_dict

    def format_message(self, message: Message) -> Dict[str, Any]:
        """
        Format a message into the format expected by Groq.

        Args:
            message (Message): The message to format.

        Returns:
            Dict[str, Any]: The formatted message.
        """
        message_dict: Dict[str, Any] = {
            "role": message.role,
            "content": message.content,
            "name": message.name,
            "tool_call_id": message.tool_call_id,
            "tool_calls": message.tool_calls,
        }
        message_dict = {k: v for k, v in message_dict.items() if v is not None}

        if (
            message.role == "system"
            and isinstance(message.content, str)
            and self.response_format is not None
            and self.response_format.get("type") == "json_object"
        ):
            # This is required by Groq to ensure the model outputs in the correct format
            message.content += "\n\nYour output should be in JSON format."

        if message.images is not None and len(message.images) > 0:
            # Ignore non-string message content
            # because we assume that the images/audio are already added to the message
            if isinstance(message.content, str):
                message_dict["content"] = [{"type": "text", "text": message.content}]
                message_dict["content"].extend(images_to_message(images=message.images))

        if message.audio is not None and len(message.audio) > 0:
            try:
                transcription_result: Any = self.transcribe_audio(
                    message.audio, model="whisper-large-v3-turbo", response_format="text"
                )

                # If there's existing content, append the transcription
                message_dict["content"] = f"Audio Transcription: {transcription_result}"
            except Exception as e:
                logger.error(f"Error transcribing audio: {str(e)}")

        if message.videos is not None:
            logger.warning("Video input is currently unsupported.")

        return message_dict

    def invoke(self, messages: List[Message]) -> ChatCompletion:
        """
        Send a chat completion request to the Groq API.

        Args:
            messages (List[Message]): A list of messages to send to the model.

        Returns:
            ChatCompletion: The chat completion response from the API.
        """
        try:
            return self.get_client().chat.completions.create(
                model=self.id,
                messages=[self.format_message(m) for m in messages],  # type: ignore
                **self.request_kwargs,
            )
        except (APIResponseValidationError, APIStatusError) as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(
                message=e.response.text, status_code=e.response.status_code, model_name=self.name, model_id=self.id
            ) from e
        except APIError as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(message=e.message, model_name=self.name, model_id=self.id) from e
        except Exception as e:
            logger.error(f"Unexpected error calling Groq API: {str(e)}")
            raise ModelProviderError(message=str(e), model_name=self.name, model_id=self.id) from e

    async def ainvoke(self, messages: List[Message]) -> ChatCompletion:
        """
        Sends an asynchronous chat completion request to the Groq API.

        Args:
            messages (List[Message]): A list of messages to send to the model.

        Returns:
            ChatCompletion: The chat completion response from the API.
        """
        try:
            return await self.get_async_client().chat.completions.create(
                model=self.id,
                messages=[self.format_message(m) for m in messages],  # type: ignore
                **self.request_kwargs,
            )
        except (APIResponseValidationError, APIStatusError) as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(
                message=e.response.text, status_code=e.response.status_code, model_name=self.name, model_id=self.id
            ) from e
        except APIError as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(message=e.message, model_name=self.name, model_id=self.id) from e
        except Exception as e:
            logger.error(f"Unexpected error calling Groq API: {str(e)}")
            raise ModelProviderError(message=str(e), model_name=self.name, model_id=self.id) from e

    def invoke_stream(self, messages: List[Message]) -> Iterator[ChatCompletionChunk]:
        """
        Send a streaming chat completion request to the Groq API.

        Args:
            messages (List[Message]): A list of messages to send to the model.

        Returns:
            Iterator[ChatCompletionChunk]: An iterator of chat completion chunks.
        """
        try:
            return self.get_client().chat.completions.create(
                model=self.id,
                messages=[self.format_message(m) for m in messages],  # type: ignore
                stream=True,
                **self.request_kwargs,
            )
        except (APIResponseValidationError, APIStatusError) as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(
                message=e.response.text, status_code=e.response.status_code, model_name=self.name, model_id=self.id
            ) from e
        except APIError as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(message=e.message, model_name=self.name, model_id=self.id) from e
        except Exception as e:
            logger.error(f"Unexpected error calling Groq API: {str(e)}")
            raise ModelProviderError(message=str(e), model_name=self.name, model_id=self.id) from e

    async def ainvoke_stream(self, messages: List[Message]) -> Any:
        """
        Sends an asynchronous streaming chat completion request to the Groq API.

        Args:
            messages (List[Message]): A list of messages to send to the model.

        Returns:
            Any: An asynchronous iterator of chat completion chunks.
        """

        try:
            stream = await self.get_async_client().chat.completions.create(
                model=self.id,
                messages=[self.format_message(m) for m in messages],  # type: ignore
                stream=True,
                **self.request_kwargs,
            )
            async for chunk in stream:  # type: ignore
                yield chunk
        except (APIResponseValidationError, APIStatusError) as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(
                message=e.response.text, status_code=e.response.status_code, model_name=self.name, model_id=self.id
            ) from e
        except APIError as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise ModelProviderError(message=e.message, model_name=self.name, model_id=self.id) from e
        except Exception as e:
            logger.error(f"Unexpected error calling Groq API: {str(e)}")
            raise ModelProviderError(message=str(e), model_name=self.name, model_id=self.id) from e

    # Override base method
    @staticmethod
    def parse_tool_calls(tool_calls_data: List[ChoiceDeltaToolCall]) -> List[Dict[str, Any]]:
        """
        Build tool calls from streamed tool call data.

        Args:
            tool_calls_data (List[ChoiceDeltaToolCall]): The tool call data to build from.

        Returns:
            List[Dict[str, Any]]: The built tool calls.
        """
        tool_calls: List[Dict[str, Any]] = []
        for _tool_call in tool_calls_data:
            _index = _tool_call.index
            _tool_call_id = _tool_call.id
            _tool_call_type = _tool_call.type
            _function_name = _tool_call.function.name if _tool_call.function else None
            _function_arguments = _tool_call.function.arguments if _tool_call.function else None

            if len(tool_calls) <= _index:
                tool_calls.extend([{}] * (_index - len(tool_calls) + 1))
            tool_call_entry = tool_calls[_index]
            if not tool_call_entry:
                tool_call_entry["id"] = _tool_call_id
                tool_call_entry["type"] = _tool_call_type
                tool_call_entry["function"] = {
                    "name": _function_name or "",
                    "arguments": _function_arguments or "",
                }
            else:
                if _function_name:
                    tool_call_entry["function"]["name"] += _function_name
                if _function_arguments:
                    tool_call_entry["function"]["arguments"] += _function_arguments
                if _tool_call_id:
                    tool_call_entry["id"] = _tool_call_id
                if _tool_call_type:
                    tool_call_entry["type"] = _tool_call_type
        return tool_calls

    def parse_provider_response(self, response: ChatCompletion) -> ModelResponse:
        """
        Parse the Groq response into a ModelResponse.

        Args:
            response: Raw response from Groq

        Returns:
            ModelResponse: Parsed response data
        """
        model_response = ModelResponse()

        # Get response message
        response_message = response.choices[0].message

        # Add role
        if response_message.role is not None:
            model_response.role = response_message.role

        # Add content
        if response_message.content is not None:
            model_response.content = response_message.content

        # Add tool calls
        if response_message.tool_calls is not None and len(response_message.tool_calls) > 0:
            try:
                model_response.tool_calls = [t.model_dump() for t in response_message.tool_calls]
            except Exception as e:
                logger.warning(f"Error processing tool calls: {e}")

        # Add usage metrics if present
        if response.usage is not None:
            model_response.response_usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "additional_metrics": {
                    "completion_time": response.usage.completion_time,
                    "prompt_time": response.usage.prompt_time,
                    "queue_time": response.usage.queue_time,
                    "total_time": response.usage.total_time,
                },
            }
        return model_response

    def parse_provider_response_delta(self, response: ChatCompletionChunk) -> ModelResponse:
        """
        Parse the Groq streaming response into ModelResponse objects.

        Args:
            response: Raw response chunk from Groq

        Returns:
            ModelResponse: Iterator of parsed response data
        """
        model_response = ModelResponse()

        if len(response.choices) > 0:
            delta: ChoiceDelta = response.choices[0].delta

            # Add content
            if delta.content is not None:
                model_response.content = delta.content

            # Add tool calls
            if delta.tool_calls is not None:
                model_response.tool_calls = delta.tool_calls  # type: ignore

        # Add usage metrics if present
        if response.x_groq is not None and response.x_groq.usage is not None:
            model_response.response_usage = {
                "input_tokens": response.x_groq.usage.prompt_tokens,
                "output_tokens": response.x_groq.usage.completion_tokens,
                "total_tokens": response.x_groq.usage.total_tokens,
                "additional_metrics": {
                    "completion_time": response.x_groq.usage.completion_time,
                    "prompt_time": response.x_groq.usage.prompt_time,
                    "queue_time": response.x_groq.usage.queue_time,
                    "total_time": response.x_groq.usage.total_time,
                },
            }

        return model_response

    def _format_audio_for_message(self, audio: Audio) -> Optional[bytes]:
        """
        Format audio data for use with the Groq API.

        Args:
            audio (Audio): The audio object to format.

        Returns:
            Optional[bytes]: The formatted audio data as bytes, or None if formatting failed.
        """
        # Case 1: Audio is a bytes object
        if audio.content and isinstance(audio.content, bytes):
            return audio.content

        # Case 2: Audio is a URL
        elif audio.url is not None and audio.audio_url_content is not None:
            return audio.audio_url_content

        # Case 3: Audio is a local file path
        elif audio.filepath is not None:
            audio_path = audio.filepath if isinstance(audio.filepath, Path) else Path(audio.filepath)
            logger.info(f"Attempting to read audio from file: {audio_path}")
            if audio_path.exists() and audio_path.is_file():
                with open(audio_path, "rb") as f:
                    content = f.read()
                    return content
            else:
                return None
        else:
            logger.warning(f"Unknown audio type or no content available: {type(audio)}")
            return None

    def transcribe_audio(
        self,
        audio_data: Union[bytes, Audio, List[Audio]],
        file_format: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: Optional[str] = "text",
        temperature: Optional[float] = None,
        model: str = "whisper-large-v3-turbo",
    ) -> Transcription:
        """
        Transcribe audio data using the Groq API.

        Args:
            audio_data: The audio data to transcribe, either as bytes, an Audio object, or a list of Audio objects.
            file_format: The format of the audio file (e.g., 'mp3', 'wav', 'ogg').
            language: The language of the audio (ISO-639-1 format).
            prompt: An optional text to guide the model's style or continue a previous audio segment.
            response_format: The format of the transcription output ('json', 'text', 'verbose_json').
            temperature: The sampling temperature, between 0 and 1.
            model: The model to use for transcription ('whisper-large-v3-turbo', 'distil-whisper-large-v3-en', 'whisper-large-v3').

        Returns:
            Transcription: The transcription response from the API.
        """
        # Process audio data if it's an Audio object
        if isinstance(audio_data, list) and len(audio_data) > 0:
            # Handle list of Audio objects
            audio_obj = audio_data[0]  # Use the first audio object
            processed_audio = self._format_audio_for_message(audio_obj)
            if processed_audio is None:
                raise ValueError("Failed to process audio data")
            audio_bytes: bytes = processed_audio
            if not file_format and audio_obj.format:
                file_format = audio_obj.format
        elif isinstance(audio_data, Audio):
            # Handle single Audio object
            processed_audio = self._format_audio_for_message(audio_data)
            if processed_audio is None:
                raise ValueError("Failed to process audio data")
            audio_bytes: bytes = processed_audio
            if not file_format and audio_data.format:
                file_format = audio_data.format
        else:
            audio_bytes: bytes = audio_data

        params: Dict[str, Any] = {}
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt
        if response_format:
            params["response_format"] = response_format
        if temperature is not None:
            params["temperature"] = temperature

        file_format = file_format or "mp3"  # Default to mp3 if no format is specified
        file_name = f"audio.{file_format}"

        client = self.get_client()

        response = client.audio.transcriptions.create(file=(file_name, audio_bytes), model=model, **params)

        return response

    async def atranscribe_audio(
        self,
        audio_data: Union[bytes, Audio, List[Audio]],
        file_format: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: Optional[str] = "json",
        temperature: Optional[float] = None,
        model: str = "whisper-large-v3-turbo",
    ) -> Transcription:
        """
        Asynchronously transcribe audio data using the Groq API.

        Args:
            audio_data: The audio data to transcribe, either as bytes, an Audio object, or a list of Audio objects.
            file_format: The format of the audio file (e.g., 'mp3', 'wav', 'ogg').
            language: The language of the audio (ISO-639-1 format).
            prompt: An optional text to guide the model's style or continue a previous audio segment.
            response_format: The format of the transcription output ('json', 'text', 'verbose_json').
            temperature: The sampling temperature, between 0 and 1.
            model: The model to use for transcription ('whisper-large-v3-turbo', 'distil-whisper-large-v3-en', 'whisper-large-v3').

        Returns:
            Transcription: The transcription response from the API.
        """
        # Process audio data if it's an Audio object
        if isinstance(audio_data, list) and len(audio_data) > 0:
            # Handle list of Audio objects
            audio_obj = audio_data[0]  # Use the first audio object
            processed_audio = self._format_audio_for_message(audio_obj)
            if processed_audio is None:
                raise ValueError("Failed to process audio data")
            audio_bytes: bytes = processed_audio
            if not file_format and audio_obj.format:
                file_format = audio_obj.format
        elif isinstance(audio_data, Audio):
            # Handle single Audio object
            processed_audio = self._format_audio_for_message(audio_data)
            if processed_audio is None:
                raise ValueError("Failed to process audio data")
            audio_bytes: bytes = processed_audio
            if not file_format and audio_data.format:
                file_format = audio_data.format
        else:
            # Handle raw bytes
            audio_bytes: bytes = audio_data

        # Prepare parameters
        params: Dict[str, Any] = {}
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt
        if response_format:
            params["response_format"] = response_format
        if temperature is not None:
            params["temperature"] = temperature

        # Create file object with proper filename
        file_name = f"audio.{file_format}" if file_format else "audio.mp3"

        # Get async client with proper API key
        client = self.get_async_client()

        response = await client.audio.transcriptions.create(file=(file_name, audio_bytes), model=model, **params)

        return response
