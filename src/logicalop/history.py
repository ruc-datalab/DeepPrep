from src.data import *
from src.tools import Logger, Config, load_prompt, parse_any_string, df_to_cotable
from src.tools.helper import GPTPOOL
from tqdm import tqdm

class DataWrangler:
    """DataWrangler class to process the query

    Functionality:
    1. Input the query (consisting of data elements and a NL query)
    2. Extract the query-related knowledge in triplets
    3. Wrangle the triplets into tables
    """
    def __init__(self):
        self.cfg = Config.load_base_config()
        self.gpt = GPTPOOL()
        self.logger = Logger(name='DataWrangler')
        self.extracter = RelationExtracter()

    def process(self, query: Query):
        knowledge_triplets = self.extract_knowledge_triplets(query)
        # tables = self.wrangle_triplets_into_tables(knowledge_triplets)
        return knowledge_triplets

    def extract_knowledge_triplets(self, query: Query):
        trips = []
        for ele in tqdm(query.eles):
            generate_trips = self.extracter.extract(ele, query.query)
            self.logger.log(generate_trips)
            trips.append(generate_trips)

        return trips


class SchemaIdentification:

    def __init__(self):
        self.cfg = Config.load_base_config()
        self.gpt = GPTPOOL()

    def identify(self, query: Query):
        # Currently, just deduce the schema with with query
        pass


class RelationExtracter:

    def __init__(self):
        self.cfg = Config.load_base_config()
        self.gpt = GPTPOOL()
        self.logger = Logger(name='InformationExtracter')
        self.MAX_TRY = 3
        self.ERR_CNT = 0
        
    def _record_error_raise(self, e):
        self.last_log = str(e)
        self.logger.log(self.last_log)
        self.ERR_CNT += 1
        if self.ERR_CNT >= self.MAX_TRY:
            self.ERR_CNT = 0
            raise ValueError(f'E: Error raised more than {self.MAX_TRY} times')
    
    def extract(self, ele: BaseElement, query:str):
        self.ERR_CNT = 0
        
        while True:
            try:
                if ele.type == 'image':
                    return self.extract_image(ele, query)
                elif ele.type == 'text':
                    return self.extract_text(ele, query)
                elif ele.type == 'table':
                    return self.extract_table(ele, query)
                elif ele.type == 'listing':
                    trips = []
                    for e in ele.elements:
                        trips += self.extract(e, query)
                    return trips
            except Exception as e:
                self._record_error_raise(e)
                continue
        
    def normalize_parsed_out(self, parsed_out:str):
        parsed_out = parsed_out.strip()
        try:
            lis = eval(parsed_out)
            if type(lis) == list:
                return lis
        except:
            pass

        # get the index of the first '[' and last ']'
        beg_idx = parsed_out.find('[')
        end_idx = parsed_out.rfind(']')
        if beg_idx == -1 or end_idx == -1:
            raise ValueError(f'Invalid parsed_out: {parsed_out}')
        # (House, close_to_MIT, True), (House, within_price_range, Unknown), (House, modern_and_attractive, True), (House, lots_of_sunlight, True)
        parsed_out = parsed_out[beg_idx+1: end_idx]

        beg_idx = parsed_out.find('(')
        end_idx = parsed_out.rfind(')')
        if beg_idx == -1 or end_idx == -1:
            raise ValueError(f'Invalid parsed_out: {parsed_out}')
        # House, close_to_MIT, True), (House, within_price_range, Unknown), (House, modern_and_attractive, True), (House, lots_of_sunlight, True
        parsed_out = parsed_out[beg_idx+1: end_idx].replace('),(', '), (')

        normalized_triplets = []
        for tup in parsed_out.split('), ('):
            if tup.count('", "') != 2:
                raise ValueError(f'One tuple has more than 3 tuples: {parsed_out}')
            subj, pred, obj = tup.split('", "')
            normalized_triplets.append((subj.strip().strip('"'), pred.strip().strip('"'), obj.strip().strip('"')))

        return normalized_triplets

    def extract_image(self, ele: ImageElement, query:str):
        template = load_prompt('./src/prompt/extract_knowledge_image.md')
        prompt = template.format(query=query, image_path = ele.filepath)
        self.logger.log('prompt:', prompt, '-'*20, sep='\n')
        out = self.gpt.query_image(ask=prompt)
        self.logger.log('out:', out, '-'*20, '', sep='\n')
        parsed_out = parse_any_string(out, code_type='python')
        return self.normalize_parsed_out(parsed_out)
    
    def extract_text(self, ele: TextElement, query:str):
        template = load_prompt('./src/prompt/extract_knowledge_text.md')
        prompt = template.format(query=query, text = ele.get_data())
        out = self.gpt.query(ask=prompt)
        parsed_out = parse_any_string(out, code_type='python')
        return self.normalize_parsed_out(parsed_out)

    def extract_table(self, ele: TableElement, query:str):
        template = load_prompt('./src/prompt/extract_knowledge_table.md')
        prompt = template.format(query=query, table=df_to_cotable(ele.get_data()))
        out = self.gpt.query(ask=prompt)
        parsed_out = parse_any_string(out, code_type='python')
        return self.normalize_parsed_out(parsed_out)