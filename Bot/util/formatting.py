def generate_code_table(col_headers, content_rows, description=''):
    """generate an ascii table with the given content
        col width is chosen to match the longest content of content_rows
        auto-split into multiple strings if table exceeds discord limit of 2000 chars

    Args:
        col_headers (list): a list with the header names, length determins column count
        content_rows (list<list>): list containing all rows, each row is list with all columns of that row
    """
    col_cnt = len(col_headers)
    row_cnt = len(content_rows)
    padding = 1

    max_row_lens = []
    for col_h in col_headers:
        max_row_lens.append(len(str(col_h)))

    for row in content_rows:
        for i, col in enumerate(row):
            max_row_lens[i] = max(max_row_lens[i], len(str(col)))
            pass

    # table width does not count outer | | 
    #             padding around vals + max col width     + separator for each col 
    table_width = (col_cnt*2)*padding + sum(max_row_lens) + (max(col_cnt-1, 0))

    
    # first construct the table header and the footer
    pad_space = ' ' * padding
    header_fields = '|'.join([str.center(str(col), max_row_lens[i]+2*padding, ' ') for i, col in enumerate(col_headers)])
    header_spacer = '|'.join(['-'*(max_row_lens[i]+padding*2) for i, _ in enumerate(col_headers)])
    
    header_str = '|{:s}|\n'.format('-'*table_width)
    header_str += f'|{header_fields}|\n'
    header_str += f'|{header_spacer}|\n'

    footer_str = f'|{header_spacer}|'


    content = ''
    for row in content_rows:
        content += '|'
        content += '|'.join(\
            [' '*padding + str.ljust(str(cell), max_row_lens[i]+padding, ' ') if (i==0) \
              else str.rjust(str(cell), max_row_lens[i]+padding, ' ') + ' '*padding \
              for i, cell in enumerate(row)])

        content += '|\n'
        pass


    table_str = description + '\n' + header_str + content + footer_str
    out_list = []

    while table_str:
        if len(table_str) < 2000-6:
            out_list.append('```' + table_str + '```')
            table_str = ''
        else:
            latest_newline = table_str[:2000-6].rfind('\n')
            out_list.append('```' + table_str[:latest_newline+1] + '```')
            table_str = table_str[latest_newline+1:]

    
    return out_list