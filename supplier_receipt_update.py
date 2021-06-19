# -*- coding: utf-8 -*-
from __future__ import print_function
from ortools.linear_solver import pywraplp
import pandas as pd
import datetime
import sys
reload(sys)
sys.setdefaultencoding('utf8')

# 占比偏离程度
supplier_limit = 0.2
rdc_limit = 0.1

# 0，1变量
M = 10000000

# 输入数据
supplier_receipt_input = pd.read_csv('supplier_sku_ratio_brand.csv')
# 记录无解sku个数
fail_cnt = 0
# 记录起始时间
starttime = datetime.datetime.now()

# 所有bu，可单独设置
bu_list = list(set(supplier_receipt_input['bu'].tolist()))

# bu_list = [1]
supplier_report = pd.DataFrame()
for bu in bu_list:
    # 所有brand，可单独设置
    supplier_bu = supplier_receipt_input.loc[supplier_receipt_input.bu == bu]
    brand_id_list = list(set(supplier_bu['brand_id'].tolist()))
    # brand_id_list = [1025]

    for brand_id in brand_id_list:
        # 所有mm_sku，可单独设置
        supplier_bu_brand = supplier_bu.loc[supplier_bu.brand_id == brand_id]
        mm_sku_id_list = list(set(supplier_bu_brand['mm_sku_id'].tolist()))
        # mm_sku_id_list = ['1512806-68a3e5516d7a7dc21fbe0e7ee13bfc1c']

        for mm_sku_id in mm_sku_id_list:
            # print(mm_sku_id_list)
            # 所有分片，可单独设置
            supplier_bu_brand_sku = supplier_bu_brand.loc[supplier_bu_brand.mm_sku_id == mm_sku_id]
            slice_list = list(set(supplier_bu_brand_sku['slice'].tolist()))
            # slice_list = [1]

            for slices in slice_list:
                supplier_bu_brand_sku_slice = supplier_bu_brand_sku.loc[supplier_bu_brand_sku.slice == slices]
                # 供应商id列表
                supplier_id = []
                # 是否必须送货
                is_send_flag = []
                # 根据份额拆分发货量
                supplier_count = []
                # 所有仓库id
                warehouse_id = []
                # 仓库需求量
                warehouse_count = []
                # 份额占比
                replenish_ratio = []
                # 仓库需求量
                count_number = 0
                # 箱规
                pac_specification = 0
                # 建立供应商与份额占比映射
                replenish_supplier_dict = {}
                # 建立仓库与仓库需求量映射
                warehouse_count_dict = {}
                # 建立仓库与是否必须送货的映射
                is_send_dict = {}

                for index, row in supplier_bu_brand_sku_slice.iterrows():
                    solver = pywraplp.Solver('SolveIntegerProblem', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
                    # 开始解析数据数据
                    supplier_id = row['supplier_id'].split('$')
                    replenish_ratio = row['replenish_ratio'].split('$')
                    is_send_flag = row['is_send_flag'].split('$')
                    pac_specification = float(row['pac_specification'])

                    cnt = 0
                    while cnt < len(supplier_id):
                        replenish_supplier_dict[supplier_id[cnt]] = replenish_ratio[cnt]
                        is_send_dict[supplier_id[cnt]] = int(is_send_flag[cnt])
                        cnt += 1
                    supplier_count_temp = row['supplier_count'].split('$')

                    for supplier_cnt in supplier_count_temp:
                        supplier_count.append(float(supplier_cnt))
                    warehouse_id = row['rdc'].split('$')
                    warehouse_count_temp = row['goods_count'].split('$')

                    for warehouse_cnt in warehouse_count_temp:
                        warehouse_count.append(float(warehouse_cnt))

                    cnt = 0
                    while cnt < len(warehouse_count):
                        warehouse_count_dict[warehouse_id[cnt]] = warehouse_count[cnt]
                        cnt += 1

                    count_number = float(row['all_count'])

                    # supplier_id = ['s1', 's2', 's3', 's4']
                    # warehouse_id = ['a', 'b', 'c']
                    # supplier_count = [60, 30, 10, 10]
                    # warehouse_count = [40, 40, 20]
                    # count_number = 100

                    # 存储供应商和仓库的量
                    s_w_dict = {}

                    cnt = 0
                    for supplier in supplier_id:
                        s_w_dict[supplier] = supplier_count[cnt]
                        cnt += 1
                    cnt = 0
                    for warehouse in warehouse_id:
                        s_w_dict[warehouse] = warehouse_count[cnt]
                        cnt += 1

                    # 决策变量
                    s_w_amount = {}
                    b_s_w_amount = {}
                    w_dummy = {}
                    s_dummy = {}

                    for s in supplier_id:
                        for w in warehouse_id:
                            s_w_amount[s, w] = solver.NumVar(0, solver.infinity(), 's_w_amount[%s][%s]' % (s, w))
                            b_s_w_amount[s, w] = solver.IntVar(0, 1, 'b_s_w_amount[%s][%s]' % (s, w))
                    for w in warehouse_id:
                        w_dummy[w] = solver.NumVar(0, solver.infinity(), 'w_dummy[%s]' % w)
                    for s in supplier_id:
                        s_dummy[s] = solver.NumVar(0, solver.infinity(), 's_dummy[%s]' % s)

                    # 需求约束
                    s_w_amount_list = []
                    s_w_amount_ratio_list = []
                    for s in supplier_id:
                        for w in warehouse_id:
                            s_w_amount_list.append(s_w_amount[s, w])
                    solver.Add(solver.Sum(s_w_amount_list) == count_number)

                    # 箱规约束
                    for s in supplier_id:
                        s_w_amount_single_list = []
                        for w in warehouse_id:
                            s_w_amount_single_list.append(s_w_amount[s, w])
                        if is_send_dict[s] == 1:
                            solver.Add(solver.Sum(s_w_amount_single_list) >= pac_specification)

                    # 仓占比约束
                    for w in warehouse_id:
                        s_amount_ratio_list = []
                        for s in supplier_id:
                            s_amount_ratio_list.append(s_w_amount[s, w])
                        if warehouse_count_dict[w] > 0:
                            solver.Add(solver.Sum(s_amount_ratio_list) >= 0.01)
                        solver.Add(solver.Sum(s_amount_ratio_list) <= s_w_dict[w] + rdc_limit * count_number)
                        solver.Add(solver.Sum(s_amount_ratio_list) >= s_w_dict[w] - rdc_limit * count_number)
                        # solver.Add(solver.Sum(s_amount_ratio_list) - s_w_dict[w] == w_dummy[w])
                        solver.Add(solver.Sum(s_amount_ratio_list) <= s_w_dict[w] + w_dummy[w])
                        solver.Add(solver.Sum(s_amount_ratio_list) >= s_w_dict[w] - w_dummy[w])

                    # 供应商占比约束
                    for s in supplier_id:
                        w_amount_ratio_list = []
                        for w in warehouse_id:
                            w_amount_ratio_list.append(s_w_amount[s, w])
                        solver.Add(solver.Sum(w_amount_ratio_list) <= s_w_dict[s] + supplier_limit * count_number)
                        solver.Add(solver.Sum(w_amount_ratio_list) >= s_w_dict[s] - supplier_limit * count_number)
                        # solver.Add(solver.Sum(w_amount_ratio_list)  - s_w_dict[s] == s_dummy[s])
                        solver.Add(solver.Sum(w_amount_ratio_list) <= s_w_dict[s] + s_dummy[s])
                        solver.Add(solver.Sum(w_amount_ratio_list) >= s_w_dict[s] - s_dummy[s])

                    # 关联两个决策变量
                    for s in supplier_id:
                        for w in warehouse_id:
                            solver.Add(s_w_amount[s, w] <= b_s_w_amount[s, w] * M)
                            solver.Add(s_w_amount[s, w] >= b_s_w_amount[s, w])

                    # solve
                    # 目标
                    b_var = []
                    s_var = []
                    w_var = []

                    # 边目标
                    for s in supplier_id:
                        for w in warehouse_id:
                            b_var.append(b_s_w_amount[s, w])

                    # 供应商占比偏离目标
                    for s in supplier_id:
                        s_var.append(s_dummy[s])

                    # 仓占比偏离目标
                    for w in warehouse_id:
                        w_var.append(w_dummy[w])

                    obj = 1000 * solver.Sum(b_var) + solver.Sum(s_var) + solver.Sum(w_var)
                    # objective

                    # 目标
                    objective = solver.Minimize(obj)
                    result_status = solver.Solve()
                    try:
                        assert result_status == pywraplp.Solver.OPTIMAL
                    except:
                        if slices == 1:
                            fail_cnt += 1
                        continue

                    # 输出目标结果
                    print(int(solver.Objective().Value()))

                    # 生成报表
                    for s in supplier_id:
                        for w in warehouse_id:
                            supplier_report_dict = {}
                            solutionValue = s_w_amount[s, w].SolutionValue()
                            if solutionValue > 0:
                                supplier_report_dict['slice'] = slices
                                supplier_report_dict['supplier_id'] = s
                                supplier_report_dict['mm_sku_id'] = mm_sku_id
                                supplier_report_dict['brand_id'] = brand_id
                                supplier_report_dict['rdc'] = w#.decode('utf-8')
                                supplier_report_dict['supplier_count'] = solutionValue
                                supplier_report_dict['count'] = count_number
                                supplier_report_dict['replenish_ratio'] = replenish_supplier_dict[s]
                                supplier_report_dict['rdc_count'] = warehouse_count_dict[w]
                                supplier_report_dict['pac_specification'] = pac_specification
                                # print(str(mm_sku_id)+'-'+str(slices)+'-'+str(s)+'-'+str(w)+'-'+str(s_w_amount[s, w].SolutionValue())+'-'+str(count_number))
                                supplier_report_temp = pd.DataFrame.from_dict(supplier_report_dict, orient='index').T
                                supplier_report = supplier_report.append(supplier_report_temp)
                                # print(supplier_report)
supplier_report_finally = supplier_report[
    ['slice', 'supplier_id', 'mm_sku_id', 'brand_id', 'rdc', 'supplier_count', 'count', 'rdc_count', 'replenish_ratio',
     'pac_specification']]
supplier_report_finally.to_csv('supplier_report_3.csv', encoding='utf-8', index=False)

# 结束时间
endtime = datetime.datetime.now()

# 打印无解个数
print(fail_cnt)
# 打印运行时间
print((endtime - starttime).seconds/60)
