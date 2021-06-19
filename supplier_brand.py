# -*- coding: utf-8 -*-
from __future__ import print_function
from ortools.linear_solver import pywraplp
import pandas as pd
import datetime
from openpyxl import Workbook
import openpyxl
import time
import timeout_decorator

# import sys   # for python 2.7
# reload(sys)
# sys.setdefaultencoding('utf8')

# 占比偏离程度
supplier_limit = 0.05
rdc_limit = 0
# 0，1变量
M = 10000000

# ### data inputs
# supplier_receipt_input = pd.read_csv('supplier_sku_date_prepare_quarter_brand.csv')
supplier_receipt_input = pd.read_csv('supplier_sku_date_prepare_quarter_brand_new.csv')


# 记录成功和失败的个数
succ_cnt = 0
fail_cnt = 0
# count for optimal or feasible solutions
optimal_cnt = 0
feasible_cnt = 0

#记录起始时间
starttime = datetime.datetime.now()  

# 所有bu，可单独设置
bu_list = list(set(supplier_receipt_input['bu'].tolist()))

supplier_report = pd.DataFrame()

for bu in bu_list:
    # 所有brand，可单独设置
    supplier_bu = supplier_receipt_input.loc[supplier_receipt_input.bu == bu]
    brand_id_list = list(set(supplier_bu['brand_id'].tolist()))
    
    for brand_id in brand_id_list:
        # 所有mm_sku，可单独设置
        supplier_bu_brand = supplier_bu.loc[supplier_bu.brand_id == brand_id]
        slice_list = list(set(supplier_bu_brand['slice'].tolist()))
                 
        for slices in slice_list:
            supplier_bu_brand_slice = supplier_bu_brand.loc[supplier_bu_brand.slice == slices]
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
            # 建立供应商理论供货字典
            supplier_dict = {}

            for index, row in supplier_bu_brand_slice.iterrows():
                solver = pywraplp.Solver('SolveIntegerProblem', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
                # 开始解析数据数据
                supplier_id = row['supplier_id'].split('$')
                replenish_ratio = row['replenish_ratio'].split('$')
#                 is_send_flag = row['is_send_flag'].split('$')   # 缺失
#                 pac_specification = float(row['pac_specification'])   #缺失
                supplier_number = row['supplier_number']
                bu_name = row['bu_name']
#                 goods_title = row['goods_title']
                brand_name = row['brand_name']

                # 定义 is_send_dict 字典
                cnt = 0 
                while cnt < len(supplier_id):
                    replenish_supplier_dict[supplier_id[cnt]] = float(replenish_ratio[cnt])
#                     is_send_dict[supplier_id[cnt]] = int(is_send_flag[cnt])
                    cnt += 1
                # 供应商id --- 供货量字典
                supplier_count_temp = row['supplier_count'].split('$')

                for supplier_cnt in supplier_count_temp:
                    supplier_count.append(float(supplier_cnt))
                
                cnt = 0
                for s in supplier_id:
                    supplier_dict[s] = supplier_count[cnt]
                    cnt += 1
                
                # 仓库id --- 需求量字典
                warehouse_id = row['rdc'].split('$')
                warehouse_count_temp = row['goods_count'].split('$')
                
                tmp = []
                for i in range(len(warehouse_count_temp)):
                    tmp.append(float(warehouse_count_temp[i]))
                warehouse_count = tmp
                    
                cnt = 0
                for w in warehouse_id:
                    warehouse_count_dict[w] = tmp[cnt]
                    cnt += 1

#                 for warehouse_cnt in warehouse_count_temp:
#                     warehouse_count.append(float(warehouse_cnt))

#                 cnt = 0 
#                 while cnt < len(warehouse_count):
#                     warehouse_count_dict[warehouse_id[cnt]] = warehouse_count[cnt]
#                     print (warehouse_count_dict)
#                     cnt += 1    
                                        
                    
                count_number = float(row['all_count'])


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
                        s_w_amount[s, w] = solver.NumVar(0, solver.infinity(), 's_w_amount[%s][%s]' % ( s, w ))
                        b_s_w_amount[s, w] = solver.IntVar(0, 1, 'b_s_w_amount[%s][%s]' % ( s, w ))
                        
                for w in warehouse_id:
                    w_dummy[w] = solver.NumVar(0, solver.infinity(), 'w_dummy[%s]' % w )
                for s in supplier_id:
                    s_dummy[s] = solver.NumVar(0, solver.infinity(), 's_dummy[%s]' % s )

                #需求约束
                s_w_amount_list = []
                s_w_amount_ratio_list = []
                for s in supplier_id:
                    for w in warehouse_id:
                        s_w_amount_list.append(s_w_amount[s, w])
                solver.Add(solver.Sum(s_w_amount_list) == count_number)

#                 #箱规约束
#                 for s in supplier_id:
#                     s_w_amount_single_list = []
#                     for w in warehouse_id:
#                         s_w_amount_single_list.append(s_w_amount[s, w])
#                     if is_send_dict[s] == 1:
#                         solver.Add(solver.Sum(s_w_amount_single_list) >= pac_specification)

                #仓占比约束
                for w in warehouse_id:
                    s_amount_ratio_list = []
                    for s in supplier_id:
                        s_amount_ratio_list.append(s_w_amount[s,w])
                    if warehouse_count_dict[w] > 0:
                        solver.Add(solver.Sum(s_amount_ratio_list) >= 0.01)
                    solver.Add(solver.Sum(s_amount_ratio_list)  <= s_w_dict[w] + rdc_limit * count_number)
                    solver.Add(solver.Sum(s_amount_ratio_list)  >= s_w_dict[w] - rdc_limit * count_number)
#                     #solver.Add(solver.Sum(s_amount_ratio_list) - s_w_dict[w] == w_dummy[w])
#                     solver.Add(solver.Sum(s_amount_ratio_list)  <= s_w_dict[w] + w_dummy[w])
#                     solver.Add(solver.Sum(s_amount_ratio_list)  >= s_w_dict[w] - w_dummy[w])

                #供应商占比约束
                for s in supplier_id:
                    w_amount_ratio_list = []
                    for w in warehouse_id:
                        w_amount_ratio_list.append(s_w_amount[s,w])
                    solver.Add(solver.Sum(w_amount_ratio_list) <= s_w_dict[s] + supplier_limit * count_number)
                    solver.Add(solver.Sum(w_amount_ratio_list) >= s_w_dict[s] - supplier_limit * count_number)
                    #solver.Add(solver.Sum(w_amount_ratio_list)  - s_w_dict[s] == s_dummy[s])
                    solver.Add(solver.Sum(w_amount_ratio_list) <= s_w_dict[s] +  replenish_supplier_dict[s] * s_dummy[s])
                    solver.Add(solver.Sum(w_amount_ratio_list) >= s_w_dict[s] -  replenish_supplier_dict[s] * s_dummy[s])


                #关联两个决策变量
                for s in supplier_id:
                    for w in warehouse_id:
                        solver.Add(s_w_amount[s, w] <= b_s_w_amount[s, w] * M)
                        solver.Add(s_w_amount[s, w] >= b_s_w_amount[s, w])

                # ### solve
                #目标
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

#                 # 仓占比偏离目标
#                 for w in warehouse_id:
#                     w_var.append(w_dummy[w])

#                 obj1 = 10 * solver.Sum(b_var) + 1000 * solver.Sum(s_var) + solver.Sum(w_var)
#                 obj2 = 1000 * solver.Sum(b_var) + solver.Sum(s_var) + solver.Sum(w_var)
#                 obj3 = solver.Sum(s_var)
                obj = 50 * solver.Sum(b_var) + 5 * solver.Sum(s_var)
                
                # objective
                # 决策目标
#                 print('solved or not')
                if supplier_number < 20:
                    objective = solver.Minimize(obj)
                    optimal_cnt += 1
                elif supplier_number >= 20:
                    objective = solver.Minimize(0)
                    feasible_cnt += 1
                result_status = solver.Solve()
                pywraplp.Solver.OPTIMAL == result_status
                
                #输出目标结果
                #print(int(solver.Objective().Value()))

                # 生成报表
                for s in supplier_id:
                    for w in warehouse_id:
                        print (s + '->' + w + '->' + str(s_w_amount[s, w].SolutionValue()))
                        supplier_report_dict = {}
                        solutionValue = s_w_amount[s, w].SolutionValue()
                        if solutionValue > 0:
                            supplier_report_dict['slice'] = slices
                            supplier_report_dict['supplier_id'] = s
                            supplier_report_dict['bu_name'] = bu_name
#                             supplier_report_dict['mm_sku_id'] = mm_sku_id
#                             supplier_report_dict['goods_title'] = goods_title
                            supplier_report_dict['brand_name'] = brand_name
                            supplier_report_dict['brand_id'] = brand_id
                            supplier_report_dict['rdc'] = w#.decode('utf-8')
                            supplier_report_dict['supplier_count'] = solutionValue
                            supplier_report_dict['count'] = count_number
                            supplier_report_dict['replenish_ratio'] = replenish_supplier_dict[s]
                            supplier_report_dict['rdc_count'] = warehouse_count_dict[w]
#                             supplier_report_dict['pac_specification'] = pac_specification
                            supplier_report_dict['supplier_number'] = supplier_number
                            #print(str(mm_sku_id)+'-'+str(slices)+'-'+str(s)+'-'+str(w)+'-'+str(s_w_amount[s, w].SolutionValue())+'-'+str(count_number))
                            supplier_report_temp = pd.DataFrame.from_dict(supplier_report_dict,orient='index').T
                            supplier_report = supplier_report.append(supplier_report_temp)
                            #print(supplier_report)
# supplier_report_finally = supplier_report[['slice','supplier_id','bu_name','goods_title','brand_id','supplier_number','rdc','supplier_count','count','rdc_count','replenish_ratio']]
supplier_report_finally = supplier_report[['slice','supplier_id','bu_name','brand_name','brand_id',
                                           'supplier_number','rdc','supplier_count','count','rdc_count','replenish_ratio']]

supplier_report_finally.to_csv('supplier_report.csv',encoding = 'utf-8' ,index=False)
writer = pd.ExcelWriter('supplier_report.xlsx')
supplier_report_finally.to_excel(writer,'details')
writer.save()

#结束时间
endtime = datetime.datetime.now()

list_aft = pd.unique(supplier_report_finally.brand_id).tolist()
list_ori = pd.unique(supplier_receipt_input.brand_id).tolist()

list(set(list_ori).difference(set(list_aft))) # 展示没有被模型解决的品牌

# rename
supplier_report_finally = supplier_report_finally.rename(columns = {'slice':'补货周期',
                                                                    'supplier_id': '供应商id',
                                                                    'bu_name': 'bu名称',
                                                                    'brand_id': '品牌id',
                                                                    'supplier_number': '供应商数量',
                                                                    'rdc': 'RDC仓',
                                                                    'supplier_count': '供应商供货量',
                                                                    'count': '全国需求',
                                                                    'rdc_count': 'RDC仓需求',
                                                                    'replenish_ratio': '供应商占比'})


supplier_report_finally.to_excel('品牌-供应商入仓结果_更新.xlsx', sheet = 'report_details')
