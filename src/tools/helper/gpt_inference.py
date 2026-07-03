import base64, re, random
import os, copy, time, yaml,json
from openai import AzureOpenAI, OpenAI, APIConnectionError
from src.tools.utils import open_json, save_json, unset_proxy
from src.tools.helper import Config, Logger

# set seed
random.seed(time.time())

"""We insert an image by add a placeholder <[IMAGE_PATH]:IMAGE_PATH> in the query. The image will be fetched and inserted into the query."""
class GPTPOOL:
    def __init__(self, cfg=None):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.logger = Logger(name='GPTPOOL', cfg=self.cfg, log_file='gpt_inference')
        self.key_file = os.path.join('./_keys', self.cfg.get('key_file'))
        self.model = self.cfg.get('llm_name')
        self.temp = self.cfg.get('temperature')
        self.root = os.path.join(self.cfg.get('filecachedir'), 'llm_query_log', self.cfg.get('version'))

        self.print_key = self.cfg.get('print_key')
        self.max_output_limit = self.cfg.get('max_output_limit')

        self.record_log = self.cfg.get('record_log')
        self.record_token = self.cfg.get('record_token')
        if not os.path.exists(self.root) and (self.record_log or self.record_token):
            os.makedirs(self.root)

        self.base_url = self.cfg.get('openai_base_url', None)
        if self.base_url is not None:
            os.environ["OPENAI_BASE_URL"] = self.base_url
        self.api_version = self.cfg.get('api_version', None)

        self.client = None
        log_path = os.path.join(self.root, 'log.json')
        self.log = open_json(log_path) if self.record_log and os.path.exists(log_path) else {}
        token_record_path = os.path.join(self.root, 'token_record.json')
        self.token_records = open_json(token_record_path) if self.record_token and os.path.exists(token_record_path) else {}
        self.resting_model = []
        self.cur_model = None

    def get_key(self):
        with open(self.key_file, 'r') as f:
            keys = [x.strip() for x in f.readlines()]

        cur_key = copy.deepcopy(keys[0])
        keys = keys[1:]+[cur_key]

        with open(self.key_file, 'w') as f:
            f.write('\n'.join(keys))

        self.cur_key = cur_key

        return cur_key

    def get_model(self):
        if isinstance(self.model, list):
            models = self.model
            if self.resting_model:
                models = [m for m in models if m not in self.resting_model]
            origin_weights = self.cfg.get('model_weights')
            weight_dict = {m: w for m, w in zip(self.model, origin_weights)}
            weights = [weight_dict[m] for m in models]
            total_weight = sum(weights)
            probs = [w / total_weight for w in weights]
            cur_model = random.choices(models, probs)[0]
            return cur_model
        return self.model


    def query(self, ask, get_thinking=False):
        max_retries = 8
        base_delay = 0.25  # seconds
        for attempt in range(max_retries):
            try:
                return self._query(ask=ask, get_thinking=get_thinking)
            except Exception as e:
                self.update_resting_model()
                self.logger.log(f"E(GPT): Connection error: {e}. Retrying in {base_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(base_delay)
                if base_delay <= 16:
                    base_delay *= 2  # Exponential backoff 
        
        raise ValueError(f'E(GPT): Failed to get a response after {max_retries} retries.')
    
    def update_resting_model(self):
        self.resting_model.append(self.cur_model)
        rest_len = max(0, len(self.model) - 2) if isinstance(self.model, list) else 0 # 保持有2个key在用
        if len(self.resting_model) > rest_len:
            self.resting_model.pop(0)


    def _query(self, ask, get_thinking=False):
        key = self.get_key()
        if key == 'EMPTY':
            unset_proxy()
        
        self.cur_model = self.get_model()
        if self.print_key:
            self.logger.log(f'cur_key: {key}')
        os.environ["OPENAI_API_KEY"] = key
        think = None
        if self.api_version is not None:
            unset_proxy()
            self.client = AzureOpenAI(
                api_key=key,
                azure_endpoint=self.base_url,
                api_version=self.api_version
            )
            completion = self.client.chat.completions.create(
                model=self.cur_model,
                messages=[{"role": "user", "content": ask}],
                # temperature=self.temp if self.temp != -1 else 1,
                max_tokens=self.max_output_limit,
                stream=False,
                extra_headers={'X-TT-LOGID': '${your_logid}'}
            )
            # content = ""
            # for chunk in completion:
            #     if chunk and chunk.choices[0].delta.content:
            #         content += chunk.choices[0].delta.content
            content = completion.choices[0].message.content
            # content = json.loads(completion.model_dump_json(indent=2))['choices'][0]['message']['content']
            ans = content
        else:
            self.client = OpenAI(
                api_key=key,
                base_url=self.base_url,
                timeout=600
            )

            completion = self.client.chat.completions.create(
                model=self.cur_model,
                messages=[{"role": "user", "content": ask}],
                temperature=self.temp if self.temp != -1 else 1,
                max_tokens=self.max_output_limit,
                timeout=600
            )
            ans = completion.choices[0].message.content
            if get_thinking:
                think = completion.choices[0].message.reasoning_content

        if self.record_log:
            cur_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.log[cur_time] = {'ask': ask, 'ans': ans}
            save_json(self.log, os.path.join(self.root, 'log.json'))

        if get_thinking:
            return ans, think
        else:
            return ans


class GPT:
    def __init__(self, cfg=None):
        self.gpt_pool = GPTPOOL(cfg)

    def query(self, messages, get_thinking=False):
        max_retries = 12
        base_delay = 0.25  # seconds
        for attempt in range(max_retries):
            try:
                return self._query(messages=messages, get_thinking=get_thinking)
            except Exception as e:
                self.gpt_pool.update_resting_model()
                self.gpt_pool.logger.log(f"E(GPT): Connection error: {e}. Retrying in {base_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(base_delay)
                if base_delay <= 32:
                    base_delay *= 2  # Exponential backoff 

        raise ValueError(f'E(GPT): Failed to get a response after {max_retries} retries.')

    def _query(self, messages, get_thinking=False):
        key = self.gpt_pool.get_key()
        if key == 'EMPTY':
            unset_proxy()
        self.gpt_pool.cur_model = self.gpt_pool.get_model()
        if self.gpt_pool.print_key:
            self.gpt_pool.logger.log(f'cur_key: {key}')
        os.environ["OPENAI_API_KEY"] = key
        think = None

        processed_messages = self._process_images_in_messages(messages)


        if self.gpt_pool.api_version is not None:
            unset_proxy()
            self.gpt_pool.client = AzureOpenAI(
                api_key=key,
                azure_endpoint=self.gpt_pool.base_url,
                api_version=self.gpt_pool.api_version
            )
            completion = self.gpt_pool.client.chat.completions.create(
                model=self.gpt_pool.cur_model,
                messages=processed_messages,
                # temperature=self.temp if self.temp != -1 else 1,
                max_tokens=self.gpt_pool.max_output_limit,
                stream=False,
                extra_headers={'X-TT-LOGID': '${your_logid}'}
            )
            # content = ""
            # for chunk in completion:
            #     if chunk and chunk.choices[0].delta.content:
            #         content += chunk.choices[0].delta.content

            content = json.loads(completion.model_dump_json(indent=2))['choices'][0]['message']['content']
            ans = content

        else:
            # OpenAI
            self.gpt_pool.client = OpenAI(
                api_key=key,
                base_url=self.gpt_pool.base_url,
                timeout=600
            )

            completion = self.gpt_pool.client.chat.completions.create(
                model=self.gpt_pool.cur_model,
                messages=processed_messages,
                temperature=self.gpt_pool.temp if self.gpt_pool.temp != -1 else 1,
                # max_tokens=self.gpt_pool.max_output_limit,
                timeout=600
            )
            ans = completion.choices[0].message.content
            if get_thinking:
                try:
                    think = completion.choices[0].message.reasoning_content
                except Exception as e:
                    think = None

        if self.gpt_pool.record_log:
            cur_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.gpt_pool.log[cur_time] = {'messages': messages, 'ans': ans}
            save_json(self.gpt_pool.log, os.path.join(self.gpt_pool.root, 'log.json'))

        if get_thinking:
            return ans, think
        else:
            return ans

    def _process_images_in_messages(self, messages):
        processed_messages = []

        for message in messages:
            if isinstance(message['content'], str):
                processed_content = self._process_image_placeholders(message['content'])
                processed_messages.append({
                    'role': message['role'],
                    'content': processed_content
                })
            elif isinstance(message['content'], list):
                processed_content = []
                for item in message['content']:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        processed_text = self._process_image_placeholders(item['text'])
                        processed_content.append({
                            'type': 'text',
                            'text': processed_text
                        })
                    else:
                        processed_content.append(item)
                processed_messages.append({
                    'role': message['role'],
                    'content': processed_content
                })
            else:
                processed_messages.append(message)

        return processed_messages

    def _process_image_placeholders(self, text):
        import re

        def replace_placeholder(match):
            image_path = match.group(1)
            try:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                if image_path.lower().endswith('.png'):
                    image_type = 'png'
                elif image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
                    image_type = 'jpeg'
                elif image_path.lower().endswith('.webp'):
                    image_type = 'webp'
                elif image_path.lower().endswith('.gif'):
                    image_type = 'gif'
                else:
                    image_type = 'png' 

                return f"data:image/{image_type};base64,{image_data}"
            except Exception as e:
                self.gpt_pool.logger.log(f"Warning: Failed to load image {image_path}: {e}")
                return match.group(0) 

        pattern = r'<\[IMAGE_PATH\]:(.*?)>'
        return re.sub(pattern, replace_placeholder, text)

