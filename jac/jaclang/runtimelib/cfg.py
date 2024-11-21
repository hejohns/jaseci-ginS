"""Genrate a control flow graph from genarated bytecode.

This pass generates a control flow graph from the bytecode generated by the previous pass.
"""
import marshal
import dis
from collections import defaultdict
from typing import List, Optional, Iterator
import graphviz
from graphviz import Digraph

class BytecodeOp:
    def __init__(self, op: int, arg: int, offset: int, argval:int, argrepr:str, is_jump_target: bool, starts_line: int = None) -> None:
        self.op = op
        self.arg = arg
        self.offset = offset
        self.argval = argval
        self.argrepr = argrepr
        self.is_jump_target= is_jump_target
        self.starts_line = starts_line
        #default the offset
        self.__offset_size = 0

    def __repr__(self):
        return f"Instr: offset={self.offset}, Opname={self.op}, arg={self.arg}, argval={self.argval}, argrepr={self.argrepr}, starts_line={self.starts_line}"
    def is_branch(self) -> bool:
        return self.op in {
            "JUMP_ABSOLUTE",
            "JUMP_FORWARD",
            "POP_JUMP_IF_TRUE",
            "POP_JUMP_IF_FALSE",
            "JUMP_IF_TRUE_OR_POP",
            "JUMP_IF_FALSE_OR_POP",
        }
    def is_relative_branch(self) -> bool:
        return self.op in {
            "FOR_ITER",
            "JUMP_FORWARD",
        }    
    def is_return(self) -> bool:
        return self.op == "RETURN_VALUE"

    def is_raise(self) -> bool:
        return self.op == "RAISE_VARARGS"
    
    def set_offset_size(self, size) -> None:
        self.__offset_size = size

    def get_offset_size(self) -> int:
        return self.__offset_size
    
    def get_next_instruction_offset(self) -> int:
        return self.__offset_size + self.offset

class Block:
    def __init__(self, id: int, instructions: List):
        self.id: int = id
        self.instructions = instructions
        self.exec_count = 0
        self.line_nos = set([instr.starts_line for instr in self.instructions if instr.starts_line != None])
        
        print(id, self.line_nos)
        
        
    def __repr__(self):
      instructions = "\n".join([str(instr) for instr in self.instructions])
      return f"bb{self.id}:\n{instructions}"

class BlockMap:
    def __init__(self) -> None:
        self.idx_to_block: Dict[int, Block] = {}

    def add_block(self, idx, block):
        self.idx_to_block[idx] = block

    def __repr__(self) -> str:
        result = []
        for block in self.idx_to_block.values():
          result.append(repr(block))
        return "\n".join(result)
    def __str__(self) -> str:
        return self.__repr__()

def disassemble_bytecode(bytecode):
    code_object = marshal.loads(bytecode)
    instructions = []
    for i, instr in enumerate(dis.get_instructions(code_object)):
        instructions.append(BytecodeOp(
        op = instr.opname, 
        arg=instr.arg,
        offset=instr.offset,
        argval=instr.argval,
        argrepr=instr.argrepr,
        is_jump_target=instr.is_jump_target,
        starts_line=instr.starts_line,
        ))
        #set offest size for calculating next instruction
        #last instruction is default of 2, but shouldn't be needed
        if i != 0:
            instruction = instructions[i-1]
            instruction.set_offset_size(instr.offset - instructions[i-1].offset)
    return instructions

def create_BBs(instructions: List[BytecodeOp]) -> BlockMap:
    block_starts = set([0])
    block_map = BlockMap()
    num_instr = len(instructions)
    
    # Create offset to index mapping
    offset_to_index = {instr.offset: idx for idx, instr in enumerate(instructions)}
    max_offset = instructions[-1].get_next_instruction_offset()
    # print(f"Offset to Index Mapping: {offset_to_index}")

    def valid_offset(offset):
        return offset >= 0 and offset <= max_offset
    # Identify all block starts
    for instr in instructions:
        if instr.is_branch() or  instr.op == "FOR_ITER":
            next_instr_offset = instr.get_next_instruction_offset()

            if 0 <= next_instr_offset <= max_offset:
                block_starts.add(next_instr_offset)
            
            #TODO: Confirm we can clean this up
            if instr.is_relative_branch():
                target_offset = instr.argval
            else:
                target_offset = instr.argval
                
            if valid_offset(target_offset):
                block_starts.add(target_offset)
        
        if instr.is_jump_target:
            block_starts.add(instr.offset)

    block_starts_ordered = sorted(block_starts)
    # print(f"Identified block starts: {block_starts_ordered}")

    for block_id, start_offset in enumerate(block_starts_ordered):
        end_offset = block_starts_ordered[block_id + 1] if block_id + 1 < len(block_starts_ordered) else instructions[-1].get_next_instruction_offset()
        start_index = offset_to_index[start_offset]
        end_index = num_instr
        
        # Find the corresponding end_index
        for offset in block_starts_ordered:
            if offset > start_offset:
                try:
                    end_index = offset_to_index[offset]
                except Exception as e:
                    print(f'Error: {e}')               
                break
        
        # Collect instructions for this block
        block_instrs = instructions[start_index:end_index]
        block_map.add_block(block_id, Block(block_id, block_instrs))
    return block_map


class CFG:
    def __init__(self, block_map:BlockMap):
        self.nodes = set()
        self.edges = {}
        self.edge_counts = {}
        self.block_map = block_map

    def add_node(self, node_id):
        self.nodes.add(node_id)
        if node_id not in self.edges:
            self.edges[node_id] = []

    def add_edge(self, from_node, to_node):
        if from_node in self.edges:
            self.edges[from_node].append(to_node)
        else:
            self.edges[from_node] = to_node
        
        self.edge_counts[(from_node, to_node)] = 0

    def display_instructions(self):
        return repr(self.block_map)
        
    def __repr__(self):
        result = []
        for node in self.nodes:
            result.append(f'Node bb{node} (exec count={self.block_map.idx_to_block[node].exec_count}):')
            if node in self.edges and self.edges[node]:
                for succ in self.edges[node]:
                    result.append(f'  -> bb{succ} (edge edec count={self.edge_counts[(node, succ)]})')
        return "\n".join(result)
def create_cfg(block_map: BlockMap) -> CFG:
    cfg = CFG(block_map)

    for block_id, block in block_map.idx_to_block.items():
        if block_id == 7:
            x = 1
        cfg.add_node(block_id)
        
        last_instr = block.instructions[-1]

        # Handle conditional jumps (e.g., POP_JUMP_IF_FALSE)
        if last_instr.is_branch():
            target_offset = last_instr.argval if not last_instr.is_relative_branch() else (last_instr.offset + last_instr.argval)
            target_block = find_block_by_offset(block_map, target_offset)
            if target_block is not None:
                cfg.add_edge(block_id, target_block)
            # Fall-through to next block if it's a conditional branch
            if last_instr.op.startswith('POP_JUMP_IF'):
                fall_through_offset = block.instructions[-1].get_next_instruction_offset()
                fall_through_block = find_block_by_offset(block_map, fall_through_offset)
                if fall_through_block is not None:
                    cfg.add_edge(block_id, fall_through_block)

        # Handle unconditional jumps (e.g., JUMP_FORWARD, JUMP_ABSOLUTE)
        elif last_instr.op.startswith("JUMP"):
            if last_instr.op == "JUMP_BACKWARD":
                target_offset = last_instr.argval if not last_instr.is_relative_branch() else (last_instr.offset - last_instr.argval)
            else:
                target_offset = last_instr.argval if not last_instr.is_relative_branch() else (last_instr.offset + last_instr.argval)
            target_block = find_block_by_offset(block_map, target_offset)
            if target_block is not None:
                cfg.add_edge(block_id, target_block)

        elif last_instr.op == "FOR_ITER":
            # Edge to loop body
            loop_body_offset = last_instr.get_next_instruction_offset()
            loop_body_block = find_block_by_offset(block_map, loop_body_offset)
            if loop_body_block is not None:
                cfg.add_edge(block_id, loop_body_block)
            # Edge to END_FOR or loop exit
            end_for_offset = last_instr.argval
            end_for_block = find_block_by_offset(block_map, end_for_offset)
            if end_for_block is not None:
                cfg.add_edge(block_id, end_for_block)

        # Handle fall-through to the next block for non-control flow instructions
        else:
            fall_through_offset = block.instructions[-1].get_next_instruction_offset()
            fall_through_block = find_block_by_offset(block_map, fall_through_offset)
            if fall_through_block is not None and fall_through_offset != last_instr.offset:
                cfg.add_edge(block_id, fall_through_block)

    return cfg

def find_block_by_offset(block_map: BlockMap, offset: int) -> int:
    for block_id, block in block_map.idx_to_block.items():
        if any(instr.offset == offset for instr in block.instructions):
            return block_id
    return None

# def disassemble_bytecode(bytecode):
#     code_object = marshal.loads(bytecode)
#     instructions = list(dis.get_instructions(code_object))
#     print(f"Disassembled bytecode for {code_object.co_name}:")
#     print(
#         "\n".join(
#             [f"{instr.offset}: {instr.opname} {instr.argval}" for instr in instructions]
#         )
#     )
#     return instructions

# Function to visualize CFG using Graphviz
def visualize_cfg(cfg: CFG):
    dot = Digraph(comment="Control Flow Graph")
    for node in cfg.nodes:
        dot.node(f"bb{node}", f"BB{node}")
    for from_node, to_nodes in cfg.edges.items():
        for to_node in to_nodes:
            dot.edge(f"bb{from_node}", f"bb{to_node}")
    return dot

# Sample list of instructions for processing
##simple=
#instructions = disassemble_bytecode(b'c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x01\xf3*\x00\x00\x00\x97\x00d\x00d\x01l\x00m\x01Z\x01\x01\x00d\x00Z\x02d\x00Z\x03e\x03d\x00k\\\x00\x00r\x02d\x02Z\x02d\x03Z\x02y\x04)\x05\xe9\x00\x00\x00\x00)\x01\xda\x0bannotations\xe9\x01\x00\x00\x00\xe9\xff\xff\xff\xffN)\x04\xda\n__future__r\x02\x00\x00\x00\xda\x01a\xda\x01x\xa9\x00\xf3\x00\x00\x00\x00\xfaP/Users/jakobtherkelsen/Documents/jaseci-ginS/jac/examples/ginsScripts/simple.jac\xfa\x08<module>r\x0b\x00\x00\x00\x01\x00\x00\x00s%\x00\x00\x00\xf0\x03\x01\x01\x01\xf5\x02\x07\x02\x03\xd8\x05\x06\x801\xd8\x05\x06\x801\xd8\x06\x07\x881\x82f\xd8\x07\x08\x80Q\xe0\x05\x07\x811r\t\x00\x00\x00')
#hot path
# instructions = disassemble_bytecode(b'c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x01\xf3T\x00\x00\x00\x97\x00d\x00d\x01l\x00m\x01Z\x01\x01\x00d\x00Z\x02d\x00Z\x03e\x02d\x02k\x02\x00\x00r\x19e\x02d\x03z\x06\x00\x00d\x00k(\x00\x00r\x03d\x04Z\x03n\x02d\x03Z\x03e\x02d\x04z\r\x00\x00Z\x02e\x02d\x02k\x02\x00\x00r\x01\x8c\x18y\x05y\x05)\x06\xe9\x00\x00\x00\x00)\x01\xda\x0bannotations\xe9\x0f\x00\x00\x00\xe9\x02\x00\x00\x00\xe9\x01\x00\x00\x00N)\x04\xda\n__future__r\x02\x00\x00\x00\xda\x01a\xda\x01b\xa9\x00\xf3\x00\x00\x00\x00\xfaR/Users/jakobtherkelsen/Documents/jaseci-ginS/jac/examples/ginsScripts/hot_path.jac\xfa\x08<module>r\x0c\x00\x00\x00\x01\x00\x00\x00sD\x00\x00\x00\xf0\x03\x01\x01\x01\xf5\x02\x0c\x02\x03\xd8\x07\x08\x801\xd8\x07\x08\x801\xd8\t\n\x88R\x8a\x16\xd8\x08\t\x88A\x89\x05\x90\x11\x8a\n\xd8\x0b\x0c\x81q\xf0\x06\x00\x0c\r\x80q\xe0\x05\x06\x88!\x81W\x80Q\xf0\x0f\x00\n\x0b\x88R\x8d\x16r\n\x00\x00\x00')
# # # #guess_game_bc = disassemble_bytecode(b'c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x01\xf3\x9e\x01\x00\x00\x97\x00d\x00Z\x00d\x01d\x02l\x01m\x02Z\x02\x01\x00d\x01d\x03l\x03m\x04Z\x05\x01\x00d\x01d\x04l\x06Z\x07d\x01d\x05l\x08m\tZ\n\x01\x00d\x01d\x06l\x0b\xad\x02\x01\x00d\x01d\x07l\x0cm\rZ\x0e\x01\x00e\x07j\x1e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00r\x05d\x01d\x04l\x10Z\x10n\x10\x02\x00e\x05d\x08e\x11d\td\nd\x04i\x00\xac\x0b\xab\x06\x00\x00\x00\x00\x00\x00\\\x01\x00\x00Z\x10\x02\x00e\nj$\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00g\x00g\x00\xac\x0c\xab\x02\x00\x00\x00\x00\x00\x00\x02\x00e\x0ed\n\xac\r\xab\x01\x00\x00\x00\x00\x00\x00\x02\x00G\x00d\x0e\x84\x00d\x0fe\nj&\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xab\x03\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00Z\x14\x02\x00e\nj$\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00g\x00g\x00\xac\x0c\xab\x02\x00\x00\x00\x00\x00\x00\x02\x00e\x0ed\n\xac\r\xab\x01\x00\x00\x00\x00\x00\x00\x02\x00G\x00d\x10\x84\x00d\x11e\x14e\nj&\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xab\x04\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00Z\x15\t\x00\x02\x00e\x15\xab\x00\x00\x00\x00\x00\x00\x00Z\x16e\x16j/\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00\x01\x00y\x04)\x12\xfa\x16A Number Guessing Game\xe9\x00\x00\x00\x00)\x01\xda\x0bannotations)\x01\xda\njac_importN)\x01\xda\nJacFeature)\x01\xda\x01*)\x01\xda\tdataclass\xda\x06random\xda\x02pyF)\x06\xda\x06target\xda\tbase_path\xda\x03lng\xda\x06absorb\xda\tmdl_alias\xda\x05items)\x02\xda\x08on_entry\xda\x07on_exit)\x01\xda\x02eqc\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x01\xf3 \x00\x00\x00\x97\x00e\x00Z\x01d\x00Z\x02d\x01Z\x03d\x05d\x02\x84\x04Z\x04d\x06d\x03\x84\x04Z\x05y\x04)\x07\xda\x04Game\xe1\x1a\x01\x00\x00\nA generic Game base class.\n\nThe obj keyword is used to define the class.\nThe can keyword is used to define methods (functions) within the class.\nThe self keyword is used to refer to the current instance of the class.\nConstructors are defined using the init method with parameters.\nc\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x01\xf3 \x00\x00\x00\x97\x00|\x01|\x00_\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x01|\x00_\x01\x00\x00\x00\x00\x00\x00\x00\x00y\x00)\x02NF)\x02\xda\x08attempts\xda\x03won)\x02\xda\x04selfr\x17\x00\x00\x00s\x02\x00\x00\x00  \xfaT/Users/jakobtherkelsen/Documents/jaseci-ginS/jac/examples/guess_game/guess_game1.jac\xda\x08__init__z\rGame.__init__\x0e\x00\x00\x00s\x10\x00\x00\x00\x80\x00\xd8\x19!\x88\x14\x8c\x1d\xd8\x14\x19\x88\x14\x8d\x18\xf3\x00\x00\x00\x00c\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x03\x00\x00\x01\xf3\x18\x00\x00\x00\x97\x00t\x01\x00\x00\x00\x00\x00\x00\x00\x00d\x01\xab\x01\x00\x00\x00\x00\x00\x00\x82\x01)\x02N\xfa&Subclasses must implement this method.)\x01\xda\x13NotImplementedError)\x01r\x19\x00\x00\x00s\x01\x00\x00\x00 r\x1a\x00\x00\x00\xda\x04playz\tGame.play\x13\x00\x00\x00s\x12\x00\x00\x00\x80\x00\xdc\x0f"\xd8\r5\xf3\x03\x02\x10\x10\xf0\x00\x02\n\x0cr\x1c\x00\x00\x00N\xa9\x04r\x17\x00\x00\x00\xda\x03int\xda\x06return\xda\x04None\xa9\x02r#\x00\x00\x00r$\x00\x00\x00)\x06\xda\x08__name__\xda\n__module__\xda\x0c__qualname__\xda\x07__doc__r\x1b\x00\x00\x00r \x00\x00\x00\xa9\x00r\x1c\x00\x00\x00r\x1a\x00\x00\x00r\x14\x00\x00\x00r\x14\x00\x00\x00\x05\x00\x00\x00s\x11\x00\x00\x00\x84\x00\xf1\x00\x07\x02\x05\xf3\x12\x03\x06\x07\xf4\n\x04\x06\x07r\x1c\x00\x00\x00r\x14\x00\x00\x00c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x01\xf36\x00\x00\x00\x87\x00\x97\x00e\x00Z\x01d\x00Z\x02d\x01Z\x03d\x05d\x06\x88\x00f\x01d\x02\x84\rZ\x04d\x07d\x03\x84\x04Z\x05d\x08d\x04\x84\x04Z\x06\x88\x00x\x01Z\x07S\x00)\t\xda\x12GuessTheNumberGame\xfa\xae\nA number guessing game. The player must guess a number between 1 and 100.\n\nThis class inherits from Game. The super() function is used to call the parent class constructor.\nc\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x03\x00\x00\x01\xf3Z\x00\x00\x00\x95\x01\x97\x00t\x00\x00\x00\x00\x00\x00\x00\x00\x00\x89\x02|\x00\x8d\x05\x00\x00|\x01\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00t\x05\x00\x00\x00\x00\x00\x00\x00\x00j\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x01d\x02\xab\x02\x00\x00\x00\x00\x00\x00|\x00_\x04\x00\x00\x00\x00\x00\x00\x00\x00y\x00)\x03N\xe9\x01\x00\x00\x00\xe9d\x00\x00\x00)\x05\xda\x05superr\x1b\x00\x00\x00r\x08\x00\x00\x00\xda\x07randint\xda\x0ecorrect_number)\x03r\x19\x00\x00\x00r\x17\x00\x00\x00\xda\t__class__s\x03\x00\x00\x00  \x80r\x1a\x00\x00\x00r\x1b\x00\x00\x00z\x1bGuessTheNumberGame.__init__ \x00\x00\x00s \x00\x00\x00\xf8\x80\x00\xde\t\x0e\x89\x1a\x90H\xd4\t\x1d\xdc\x1f%\x9f~\x99~\xa8a\xb0\x13\xd3\x1f5\x88\x14\xd5\t\x1cr\x1c\x00\x00\x00c\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x00\x00\x00\x03\x00\x00\x01\xf3\xf4\x00\x00\x00\x97\x00|\x00j\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x01kD\x00\x00rQt\x03\x00\x00\x00\x00\x00\x00\x00\x00d\x02\xab\x01\x00\x00\x00\x00\x00\x00}\x01|\x01j\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xab\x00\x00\x00\x00\x00\x00\x00r\x1b|\x00j\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00t\t\x00\x00\x00\x00\x00\x00\x00\x00|\x01\xab\x01\x00\x00\x00\x00\x00\x00\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00n\x0bt\x0b\x00\x00\x00\x00\x00\x00\x00\x00d\x03\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00|\x00j\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x01kD\x00\x00r\x01\x8cQ|\x00j\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00s\x0ct\x0b\x00\x00\x00\x00\x00\x00\x00\x00d\x04\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00y\x00y\x00)\x05Nr\x02\x00\x00\x00\xfa"Guess a number between 1 and 100: \xfa%That\'s not a valid number! Try again.\xfa:Sorry, you didn\'t guess the number. Better luck next time!)\x07r\x17\x00\x00\x00\xda\x05input\xda\x07isdigit\xda\rprocess_guessr"\x00\x00\x00\xda\x05printr\x18\x00\x00\x00\xa9\x02r\x19\x00\x00\x00\xda\x05guesss\x02\x00\x00\x00  r\x1a\x00\x00\x00\xfa\x04playz\x17GuessTheNumberGame.play%\x00\x00\x00sd\x00\x00\x00\x80\x00\xe0\x0f\x13\x8f}\x89}\x98q\xd2\x0f \xdc\x15\x1a\xd0\x1b?\xd3\x15@\x88U\xd8\x10\x15\x97\r\x91\r\x94\x0f\xd8\x11\x15\xd7\x11#\xd1\x11#\xa4C\xa8\x05\xa3J\xd5\x11/\xe4\x11\x16\xd0\x17>\xd4\x11?\xf0\x0b\x00\x10\x14\x8f}\x89}\x98q\xd3\x0f \xf0\x10\x00\x11\x15\x97\x08\x92\x08\xdc\r\x12\xd8\x11M\xf5\x03\x02\x0e\x0f\xf0\x03\x00\x11\x19r\x1c\x00\x00\x00c\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x00\x00\x00\x03\x00\x00\x01\xf3\xfe\x00\x00\x00\x97\x00|\x01|\x00j\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00kD\x00\x00r\x0ct\x03\x00\x00\x00\x00\x00\x00\x00\x00d\x01\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00n4|\x01|\x00j\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00k\x02\x00\x00r\x0ct\x03\x00\x00\x00\x00\x00\x00\x00\x00d\x02\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00n\x19t\x03\x00\x00\x00\x00\x00\x00\x00\x00d\x03\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00d\x04|\x00_\x02\x00\x00\x00\x00\x00\x00\x00\x00d\x05|\x00_\x03\x00\x00\x00\x00\x00\x00\x00\x00|\x00x\x01j\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x06z\x17\x00\x00c\x02_\x02\x00\x00\x00\x00\x00\x00\x00\x00t\x03\x00\x00\x00\x00\x00\x00\x00\x00d\x07|\x00j\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x9b\x00d\x08\x9d\x03\xab\x01\x00\x00\x00\x00\x00\x00\x01\x00y\x00)\tN\xfa\tToo high!\xfa\x08Too low!\xfa\'Congratulations! You guessed correctly.r\x02\x00\x00\x00Tr/\x00\x00\x00\xfa\tYou have \xfa\x0f attempts left.)\x04r3\x00\x00\x00r<\x00\x00\x00r\x17\x00\x00\x00r\x18\x00\x00\x00r=\x00\x00\x00s\x02\x00\x00\x00  r\x1a\x00\x00\x00\xfa\rprocess_guessz GuessTheNumberGame.process_guess6\x00\x00\x00se\x00\x00\x00\x80\x00\xd8\x0c\x11\x90D\xd7\x14\'\xd1\x14\'\xd2\x0c\'\xdc\r\x12\x90;\xd5\r\x1f\xd8\x10\x15\x98\x04\xd7\x18+\xd1\x18+\xd2\x10+\xdc\r\x12\x90:\xd5\r\x1e\xe4\r\x12\xd0\x13<\xd4\r=\xd8\x1d\x1e\x88T\x8c]\xd8\x18\x1c\x88T\x8cX\xe0\t\r\x8f\x1d\x8a\x1d\x98!\xd1\t\x1c\x8d\x1d\xdc\t\x0e\xd0\x0f9\x984\x9f=\x9a=\xd1\x0f9\xd5\t:r\x1c\x00\x00\x00)\x01\xe9\n\x00\x00\x00r!\x00\x00\x00r%\x00\x00\x00)\x04r>\x00\x00\x00r"\x00\x00\x00r#\x00\x00\x00r$\x00\x00\x00)\x08r&\x00\x00\x00r\'\x00\x00\x00r(\x00\x00\x00r)\x00\x00\x00r\x1b\x00\x00\x00r \x00\x00\x00r;\x00\x00\x00\xda\r__classcell__)\x01r4\x00\x00\x00s\x01\x00\x00\x00@r\x1a\x00\x00\x00r,\x00\x00\x00r,\x00\x00\x00\x1a\x00\x00\x00s\x17\x00\x00\x00\xf8\x84\x00\xf1\x00\x04\x02\x05\xf6\x0c\x03\x06\x07\xf3\n\x0f\x06\x07\xf7"\x0c\x06\x07r\x1c\x00\x00\x00r,\x00\x00\x00)\x18r)\x00\x00\x00\xda\n__future__r\x03\x00\x00\x00\xda\x07jaclangr\x04\x00\x00\x00\xda\x0e__jac_import__\xda\x06typing\xda\x08_jac_typ\xda\x16jaclang.plugin.featurer\x05\x00\x00\x00\xda\x04_Jac\xda\x16jaclang.plugin.builtin\xda\x0bdataclassesr\x07\x00\x00\x00\xda\x11__jac_dataclass__\xda\rTYPE_CHECKINGr\x08\x00\x00\x00\xda\x08__file__\xda\x08make_obj\xda\x03Objr\x14\x00\x00\x00r,\x00\x00\x00\xda\x04gamer \x00\x00\x00r*\x00\x00\x00r\x1c\x00\x00\x00r\x1a\x00\x00\x00\xda\x08<module>rX\x00\x00\x00\x01\x00\x00\x00s\xaa\x00\x00\x00\xf0\x03\x01\x01\x01\xd9\x01\x1d\xf7\x00K\x01\x02\x03\xf7\x00K\x01\x02\x03\xf7\x00K\x01\x02\x03\xf7\x00K\x01\x02\x03\xf0\x00K\x01\x02\x03\xe7\x01\x12\xd7\x01\x12\xd4\x01\x12\x80s\xd7\x01\x12\xd2\x01\x12\xf1\x04\x13\x02\x03\xef&\xe9\x00\xf7\'\x13\x02\x03\xf7\x00\x13\x02\x03\xf4\x00\x13\x02\x03\xef&\xe9\x00\xf7\'\x13\x02\x03\xf4\x00\x13\x02\x03\xf1*)\x02\x03\xefR\x01\xe9\x00\xf7S\x01)\x02\x03\xf7\x00)\x02\x03\xf3\x00)\x02\x03\xf0\n\x00\x1a\x1e\xf0\x0b)\x02\x03\xefR\x01\xe9\x00\xf7S\x01)\x02\x03\xf4\x00)\x02\x03\xf0X\x01\x02\x02\x05\xf1\x08\x00\r\x1f\xd3\x0c \x80T\xd8\x05\t\x87Y\x81Y\x85[r\x1c\x00\x00\x00')
# BBs = create_BBs(instructions)
# print(BBs)

# cfg = create_cfg(BBs)
# print("\nControl Flow Graph (CFG):")
# print(cfg)

# # Visualize CFG
# dot = visualize_cfg(cfg)
# dot.render('cfg.gv', view=True)