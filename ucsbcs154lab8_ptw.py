import pyrtl

main_memory = pyrtl.MemBlock(bitwidth=32, addrwidth=32, name="main_mem")

virtual_addr_i        = pyrtl.Input(bitwidth=32, name="virtual_addr_i")
new_req_i             = pyrtl.Input(bitwidth=1,  name="new_req_i")
reset_i               = pyrtl.Input(bitwidth=1,  name="reset_i")
req_type_i            = pyrtl.Input(bitwidth=1,  name="req_type_i")

physical_addr_o       = pyrtl.Output(bitwidth=32,name="physical_addr_o")
dirty_o               = pyrtl.Output(bitwidth=1, name="dirty_o")
valid_o               = pyrtl.Output(bitwidth=1, name="valid_o")
ref_o                 = pyrtl.Output(bitwidth=1, name="ref_o")
error_code_o          = pyrtl.Output(bitwidth=3, name="error_code_o")
finished_walk_o       = pyrtl.Output(bitwidth=1, name="finished_walk_o")

page_fault          = pyrtl.WireVector(bitwidth=1, name="page_fault")
state               = pyrtl.Register(bitwidth=2, name="state")
base_register       = pyrtl.Const(0x3FFBFF, bitwidth=22)

####### START: KATIE DID THIS #######
virtual_addr_reg = pyrtl.Register(bitwidth = 32, name = "virtual_addr_reg")
req_type_reg = pyrtl.Register(bitwidth = 1, name = "req_type_reg")
# step_addr_reg = pyrtl.Register(bitwidth = 32, name = "step_addr_reg")
value_reg = pyrtl.Register(bitwidth = 32, name = "value_reg")
value_wv = pyrtl.WireVector(bitwidth = 32, name = "value_wv")
virtual_addr_wv = pyrtl.WireVector(bitwidth = 32, name = "virtual_addr_wv")
req_type_wv = pyrtl.WireVector(bitwidth = 1, name = "req_type_wv")
adr_wv =  pyrtl.WireVector(bitwidth = 32, name = "adr_wv")
adr_reg =  pyrtl.Register(bitwidth = 32, name = "adr_reg")

# step_addr_wv  = pyrtl.WireVector(bitwidth = 32, name = "step_wv")
# if state is 0 accept new req else decline
req_type_wv <<= req_type_i
req_type_reg.next <<= pyrtl.select(state == 0, req_type_wv, req_type_reg)

# if state is 0 get new virtual_addr else decline
virtual_addr_wv <<= virtual_addr_i
virtual_addr_reg.next <<= pyrtl.select(state == 0, virtual_addr_wv, virtual_addr_reg)

# step address is the address at each step. 
""" step_addr_wv <<= pyrtl.select(state == 0)
step_addr_reg.next = pyrtl.select(state == 0, step_addr_wv, step_addr_reg) """


# Step 1 : Split input into the three offsets
offset_1 = virtual_addr_i[22:32]
offset_2 = virtual_addr_i[12:22]
offset_3 = virtual_addr_i[0:12]


## initialzing vallue at each step
adr_wv <<= pyrtl.select(state == 0, pyrtl.concat(base_register, offset_1), 
                         pyrtl.select(state==1, pyrtl.concat(value_wv[0:22], offset_2), 
                                      pyrtl.select(state == 2, pyrtl.concat(value_wv[0:20], offset_3), 0)))
adr_reg.next <<= adr_wv
value_wv <<= main_memory[adr_reg] # value is the value at the address. address is adr_reg
value_reg.next <<= value_wv # value is the value at the address. address is adr_reg
valid_wv = pyrtl.WireVector(bitwidth = 1, name = "valid_wv")
dirty_wv = pyrtl.WireVector(bitwidth = 1, name = "dirty_wv")
ref_wv = pyrtl.WireVector(bitwidth = 1, name = "ref_wv")
writeable_wv = pyrtl.WireVector(bitwidth = 1, name = "writeable_wv")
readable_wv = pyrtl.WireVector(bitwidth = 1, name = "readable_wv")

valid_wv <<= value_wv[31:32]
dirty_wv <<=  value_wv[30:31]
ref_wv <<= value_wv[29:30]
writeable_wv <<= value_wv[28:29]
readable_wv <<= value_wv[27:28]
# Step 2 : UPDATE STATE according to state diagram in instructions
# if state = 0 and new request, then step 1.
# if state = 1 nd valid, query 2nd and step to second. if page fault then go to first
# 3 if 3 then go to 1. 
state.next <<= pyrtl.select((state == 0) & (~page_fault) & (~reset_i) & (new_req_i), 1, pyrtl.select((state == 1) & (~page_fault) & (~reset_i), 2, 0))

####### END: KATIE DID THIS #######

# Step 3 : Determine physical address by walking the page table structure


# OUTPUTS 
page_fault <<= ((state != 0) & ((state==1 & ~valid_wv) | (state==2 & ~valid_wv)))

# Step 4 : Determine the outputs based on the last level of the page table walk

dirty_o <<= ((state == 0) | (state == 1 & dirty_wv) | (state == 2& dirty_wv))
valid_o <<= ((state == 0) | (state == 1 & valid_wv) | (state == 2& valid_wv))
ref_o <<= ((state == 0) | (state == 1 & ref_wv) | (state == 2& ref_wv))

physical_addr_o <<= pyrtl.select((state == 2) & ~page_fault, adr_wv, 0)
finished_walk_o <<= pyrtl.select(page_fault, 1, 0)
error_code_o <<= pyrtl.select(page_fault, 0b01, 
                              pyrtl.select((state == 2) & (req_type_i == 0) & ~readable_wv, 0b100, 
                                           pyrtl.select((state == 2) & (req_type_i == 1) & ~writeable_wv, 0b010, 0)))


if __name__ == "__main__":

    """
    These memory addresses correspond to the test that we walk through in the instructions
    This just does a basic walk from the first level to the last level where no errors should occur
    """
    memory = {
        4293918528: 0xC43FFC6B,
        4294029192: 0xAC061D26,
        1641180595: 0xDEADBEEF
    }

    sim_trace = pyrtl.SimulationTrace()
    sim = pyrtl.Simulation(tracer=sim_trace, memory_value_map={main_memory: memory})

    for i in range(3):
        sim.step({
            new_req_i: 1,
            reset_i: 0,
            virtual_addr_i: 0xD0388DB3,
            req_type_i: 0
    })

    sim_trace.render_trace(symbol_len=20)

    assert (sim_trace.trace["physical_addr_o"][-1] == 0x61d26db3)
    assert (sim_trace.trace["error_code_o"][-1] == 0x0)
    assert (sim_trace.trace["dirty_o"][-1] == 0x0)