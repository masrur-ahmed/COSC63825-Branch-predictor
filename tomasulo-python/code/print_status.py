# Qing 
# 21st May 2017

from init import to_single

# function: print RS/ROB status
def ps(unit):
    if(len(unit)==0):
        print('empty!')
    else:
        # get all fields in namedtuple
        fields_list = unit[0]._fields
        for unit_item in unit:
            print ('******')
            for field in fields_list:
                print(field+': ', str(getattr(unit_item, field)))

# function: print single namedtuple
def pss(snt):
    fields_list = snt._fields
    for field in fields_list:
        print (field+': ', str(getattr(snt, field)))


# function: format a value; single precision values (from memory) are printed
# with the shortest decimal that gives the same 32-bit float, so 3.4 prints as 3.4
def format_value(value):
    if isinstance(value, float):
        for digits in range(1, 10):
            text = '%.*g' % (digits, value)
            if (to_single(float(text)) == value) & ('e' not in text):
                return text
        return '%.10g' % value
    return str(value)

# function: print register values, 8 registers per row
def print_registers(reg_int, reg_fp):
    print('REGISTER VALUES')
    for prefix, values in (('R', reg_int), ('F', reg_fp)):
        for start in range(0, 32, 8):
            print('        ' + ''.join((prefix+str(i)).ljust(11) + ' ' for i in range(start, start+8)))
            print('value:  ' + ''.join(format_value(v).ljust(11) + ' ' for v in values[start:start+8]))

# function: print non-zero memory values
def print_memory(memory):
    print('NON-ZERO MEMORY VALUES')
    print('Addresses'.ljust(12) + 'Values')
    for address in range(len(memory)):
        if memory[address] != 0:
            print(str(address).ljust(12) + format_value(memory[address]))
