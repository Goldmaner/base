-- Script de exclusão de duplicatas exatas em public.parcerias_sei
-- Gerado em: 19/01/2026 17:57:29
-- ATENÇÃO: Mantém o registro com menor ID, exclui os demais

BEGIN;

-- Duplicata: Termo=TCL/003/2016/SMPM/CPM, SEI=145341088, Aditamento=12
-- Total de registros: 13 | Mantendo ID 72, excluindo IDs: [73, 74, 75, 76, 77, 78, 79, 80, 2665, 3361, 3404, 3696]
DELETE FROM public.parcerias_sei WHERE id IN (73,74,75,76,77,78,79,80,2665,3361,3404,3696);

-- Duplicata: Termo=TCL/014/2023/SMDHC/SESANA, SEI=109146155, Aditamento=1
-- Total de registros: 8 | Mantendo ID 2405, excluindo IDs: [2658, 3028, 3211, 3239, 3630, 3843, 3844]
DELETE FROM public.parcerias_sei WHERE id IN (2658,3028,3211,3239,3630,3843,3844);

-- Duplicata: Termo=TCL/030/2023/SMDHC/SESANA, SEI=141073939, Aditamento=2
-- Total de registros: 8 | Mantendo ID 2415, excluindo IDs: [3036, 3200, 3251, 3252, 3622, 3822, 3823]
DELETE FROM public.parcerias_sei WHERE id IN (3036,3200,3251,3252,3622,3822,3823);

-- Duplicata: Termo=TCL/009/2023/SMDHC/SESANA, SEI=130878572, Aditamento=2
-- Total de registros: 7 | Mantendo ID 2397, excluindo IDs: [3022, 3214, 3230, 3626, 3832, 3833]
DELETE FROM public.parcerias_sei WHERE id IN (3022,3214,3230,3626,3832,3833);

-- Duplicata: Termo=TCL/008/2024/SMDHC/SESANA, SEI=123038762, Aditamento=1
-- Total de registros: 7 | Mantendo ID 2787, excluindo IDs: [3080, 3521, 3559, 3815, 3816, 3820]
DELETE FROM public.parcerias_sei WHERE id IN (3080,3521,3559,3815,3816,3820);

-- Duplicata: Termo=TCL/010/2023/SMDHC/SESANA, SEI=088128964, Aditamento=1
-- Total de registros: 6 | Mantendo ID 2400, excluindo IDs: [2494, 3043, 3213, 3226, 3627]
DELETE FROM public.parcerias_sei WHERE id IN (2494,3043,3213,3226,3627);

-- Duplicata: Termo=TCL/013/2023/SMDHC/SESANA, SEI=109145664, Aditamento=1
-- Total de registros: 6 | Mantendo ID 2404, excluindo IDs: [2802, 3027, 3212, 3222, 3629]
DELETE FROM public.parcerias_sei WHERE id IN (2802,3027,3212,3222,3629);

-- Duplicata: Termo=TCL/011/2024/SMDHC/SESANA, SEI=124197999, Aditamento=1
-- Total de registros: 6 | Mantendo ID 2833, excluindo IDs: [3083, 3537, 3587, 3813, 3819]
DELETE FROM public.parcerias_sei WHERE id IN (3083,3537,3587,3813,3819);

-- Duplicata: Termo=TCL/006/2023/SMDHC/SESANA, SEI=108367875, Aditamento=1
-- Total de registros: 5 | Mantendo ID 2394, excluindo IDs: [3019, 3208, 3231, 3623]
DELETE FROM public.parcerias_sei WHERE id IN (3019,3208,3231,3623);

-- Duplicata: Termo=TCL/007/2023/SMDHC/SESANA, SEI=109141453, Aditamento=1
-- Total de registros: 5 | Mantendo ID 2395, excluindo IDs: [3020, 3209, 3223, 3624]
DELETE FROM public.parcerias_sei WHERE id IN (3020,3209,3223,3624);

-- Duplicata: Termo=TCL/008/2023/SMDHC/SESANA, SEI=109141961, Aditamento=1
-- Total de registros: 5 | Mantendo ID 2396, excluindo IDs: [3021, 3205, 3229, 3625]
DELETE FROM public.parcerias_sei WHERE id IN (3021,3205,3229,3625);

-- Duplicata: Termo=TCL/011/2023/SMDHC/SESANA, SEI=108383596, Aditamento=1
-- Total de registros: 5 | Mantendo ID 2401, excluindo IDs: [3012, 3206, 3253, 3628]
DELETE FROM public.parcerias_sei WHERE id IN (3012,3206,3253,3628);

-- Duplicata: Termo=TCL/006/2024/SMDHC/SESANA, SEI=126901589, Aditamento=2
-- Total de registros: 4 | Mantendo ID 2786, excluindo IDs: [3079, 3515, 3557]
DELETE FROM public.parcerias_sei WHERE id IN (3079,3515,3557);

-- Duplicata: Termo=TCL/003/2024/SMDHC/SESANA, SEI=123038400, Aditamento=1
-- Total de registros: 4 | Mantendo ID 2783, excluindo IDs: [3076, 3520, 3560]
DELETE FROM public.parcerias_sei WHERE id IN (3076,3520,3560);

-- Duplicata: Termo=TCL/007/2024/SMDHC/SESANA, SEI=127087813, Aditamento=2
-- Total de registros: 4 | Mantendo ID 2789, excluindo IDs: [3082, 3517, 3561]
DELETE FROM public.parcerias_sei WHERE id IN (3082,3517,3561);

-- Duplicata: Termo=TCL/001/2024/SMDHC/SESANA, SEI=127085658, Aditamento=2
-- Total de registros: 4 | Mantendo ID 2781, excluindo IDs: [3074, 3518, 3558]
DELETE FROM public.parcerias_sei WHERE id IN (3074,3518,3558);

-- Duplicata: Termo=TCL/020/2024/SMDHC/CPLGBTI, SEI=120042159, Aditamento=1
-- Total de registros: 4 | Mantendo ID 3446, excluindo IDs: [3533, 3534, 3569]
DELETE FROM public.parcerias_sei WHERE id IN (3533,3534,3569);

-- Duplicata: Termo=TCL/005/2024/SMDHC/SESANA, SEI=123036352, Aditamento=1
-- Total de registros: 4 | Mantendo ID 2785, excluindo IDs: [3078, 3514, 3556]
DELETE FROM public.parcerias_sei WHERE id IN (3078,3514,3556);

-- Duplicata: Termo=TCL/009/2024/SMDHC/SESANA, SEI=127581779, Aditamento=2
-- Total de registros: 4 | Mantendo ID 2788, excluindo IDs: [3081, 3516, 3562]
DELETE FROM public.parcerias_sei WHERE id IN (3081,3516,3562);

-- Duplicata: Termo=TFM/150/2024/SMDHC/FUMCAD, SEI=127401346, Aditamento=1
-- Total de registros: 3 | Mantendo ID 3368, excluindo IDs: [3648, 3661]
DELETE FROM public.parcerias_sei WHERE id IN (3648,3661);

-- Duplicata: Termo=TFM/032/2024/SMDHC/FUMCAD, SEI=126990255, Aditamento=1
-- Total de registros: 3 | Mantendo ID 2876, excluindo IDs: [3572, 3732]
DELETE FROM public.parcerias_sei WHERE id IN (3572,3732);

-- Duplicata: Termo=TCL/023/2024/SMDHC/CPLGBTI, SEI=120508486, Aditamento=1
-- Total de registros: 3 | Mantendo ID 3462, excluindo IDs: [3538, 3811]
DELETE FROM public.parcerias_sei WHERE id IN (3538,3811);

-- Duplicata: Termo=TFM/054/2021/SMDHC/FMID, SEI=100019477, Aditamento=1
-- Total de registros: 3 | Mantendo ID 906, excluindo IDs: [3532, 3817]
DELETE FROM public.parcerias_sei WHERE id IN (3532,3817);

-- Duplicata: Termo=TCL/103/2020/SMADS/CPM, SEI=147652723, Aditamento=4
-- Total de registros: 3 | Mantendo ID 3416, excluindo IDs: [3548, 3742]
DELETE FROM public.parcerias_sei WHERE id IN (3548,3742);

-- Duplicata: Termo=TCL/503/2023/SMADS/CPM, SEI=148462289, Aditamento=4
-- Total de registros: 3 | Mantendo ID 3358, excluindo IDs: [3476, 3801]
DELETE FROM public.parcerias_sei WHERE id IN (3476,3801);

-- Duplicata: Termo=TFM/239/2024/SMDHC/CPPSR, SEI=128026079, Aditamento=1
-- Total de registros: 3 | Mantendo ID 3468, excluindo IDs: [3578, 3686]
DELETE FROM public.parcerias_sei WHERE id IN (3578,3686);

-- Duplicata: Termo=TFM/015/2024/SMDHC/FUMCAD, SEI=127864583, Aditamento=1
-- Total de registros: 3 | Mantendo ID 2828, excluindo IDs: [3150, 3586]
DELETE FROM public.parcerias_sei WHERE id IN (3150,3586);

-- Duplicata: Termo=TFM/240/2024/SMDHC/CPIR, SEI=131360858, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3469, excluindo IDs: [3646]
DELETE FROM public.parcerias_sei WHERE id IN (3646);

-- Duplicata: Termo=TCV/001/2018/SMDHC/FUMCAD, SEI=5922889, Aditamento=-
-- Total de registros: 2 | Mantendo ID 424, excluindo IDs: [3658]
DELETE FROM public.parcerias_sei WHERE id IN (3658);

-- Duplicata: Termo=TFM/007/2024/SMDHC/FUMCAD, SEI=127866746, Aditamento=1
-- Total de registros: 2 | Mantendo ID 2908, excluindo IDs: [3577]
DELETE FROM public.parcerias_sei WHERE id IN (3577);

-- Duplicata: Termo=TFM/018/2025/SMDHC/FUMCAD, SEI=146478018, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3523, excluindo IDs: [3734]
DELETE FROM public.parcerias_sei WHERE id IN (3734);

-- Duplicata: Termo=TFM/035/2025/SMDHC/FUMCAD, SEI=146480385, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3555, excluindo IDs: [3733]
DELETE FROM public.parcerias_sei WHERE id IN (3733);

-- Duplicata: Termo=TFM/043/2025/SMDHC/FUMCAD, SEI=146972527, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3576, excluindo IDs: [3727]
DELETE FROM public.parcerias_sei WHERE id IN (3727);

-- Duplicata: Termo=TFM/057/2025/SMDHC/CPJ, SEI=146998964, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3602, excluindo IDs: [3728]
DELETE FROM public.parcerias_sei WHERE id IN (3728);

-- Duplicata: Termo=TFM/063/2025/SMDHC/CPCA, SEI=146585433, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3610, excluindo IDs: [3731]
DELETE FROM public.parcerias_sei WHERE id IN (3731);

-- Duplicata: Termo=TFM/083/2025/SMDHC/CPPI, SEI=148556484, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3669, excluindo IDs: [3792]
DELETE FROM public.parcerias_sei WHERE id IN (3792);

-- Duplicata: Termo=TFM/084/2025/SMDHC/CPM, SEI=148690353, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3681, excluindo IDs: [3790]
DELETE FROM public.parcerias_sei WHERE id IN (3790);

-- Duplicata: Termo=TFM/089/2025/SMDHC/CPM, SEI=148303323, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3676, excluindo IDs: [3769]
DELETE FROM public.parcerias_sei WHERE id IN (3769);

-- Duplicata: Termo=TFM/104/2024/SMDHC/CPCA, SEI=141718314, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3217, excluindo IDs: [3662]
DELETE FROM public.parcerias_sei WHERE id IN (3662);

-- Duplicata: Termo=TFM/111/2025/SMDHC/CPPI, SEI=148686268, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3713, excluindo IDs: [3793]
DELETE FROM public.parcerias_sei WHERE id IN (3793);

-- Duplicata: Termo=TFM/147/2024/SMDHC/CPCA, SEI=142945495, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3323, excluindo IDs: [3679]
DELETE FROM public.parcerias_sei WHERE id IN (3679);

-- Duplicata: Termo=TFM/183/2024/SMDHC/CPM, SEI=123411838, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3338, excluindo IDs: [3542]
DELETE FROM public.parcerias_sei WHERE id IN (3542);

-- Duplicata: Termo=TFM/194/2024/SMDHC/CPM, SEI=125050398, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3374, excluindo IDs: [3544]
DELETE FROM public.parcerias_sei WHERE id IN (3544);

-- Duplicata: Termo=TFM/196/2024/SMDHC/CPM, SEI=146972527, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3360, excluindo IDs: [3703]
DELETE FROM public.parcerias_sei WHERE id IN (3703);

-- Duplicata: Termo=TFM/209/2024/SMDHC/CPPSR, SEI=125103693, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3399, excluindo IDs: [3545]
DELETE FROM public.parcerias_sei WHERE id IN (3545);

-- Duplicata: Termo=TFM/210/2024/SMDHC/CPPSR, SEI=122541854, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3398, excluindo IDs: [3519]
DELETE FROM public.parcerias_sei WHERE id IN (3519);

-- Duplicata: Termo=TFM/219/2024/SMDHC/CPPI, SEI=123948728, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3449, excluindo IDs: [3543]
DELETE FROM public.parcerias_sei WHERE id IN (3543);

-- Duplicata: Termo=TFM/222/2024/SMDHC/CPIR, SEI=144380069, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3436, excluindo IDs: [3684]
DELETE FROM public.parcerias_sei WHERE id IN (3684);

-- Duplicata: Termo=TFM/232/2024/SMDHC/CPJ, SEI=127290865, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3454, excluindo IDs: [3565]
DELETE FROM public.parcerias_sei WHERE id IN (3565);

-- Duplicata: Termo=TFM/233/2024/SMDHC/CPCA, SEI=141528012, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3460, excluindo IDs: [3653]
DELETE FROM public.parcerias_sei WHERE id IN (3653);

-- Duplicata: Termo=TFM/234/2024/SMDHC/CPCA, SEI=141232758, Aditamento=1
-- Total de registros: 2 | Mantendo ID 3464, excluindo IDs: [3645]
DELETE FROM public.parcerias_sei WHERE id IN (3645);

COMMIT;

-- Total de registros a excluir: 130
