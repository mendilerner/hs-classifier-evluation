with cte as 
(
       SELECT pf.LeadDocumentID
         FROM [CustomsDWH_Pilot].[FCT].[Evaluation_fact_ProceduralFault] pf
         join [Customs_Pilot].[Shared].[General_enum_GovernmentProcedureType] gpt
              on pf.Declaration_GovernmentProcedureTypeID = gpt.id
         where [FelonyTypeID] = 4 --סיווג
         and gpt.name like '%מסחרי%'
         and Date > '2025-01-01'
),
cte2 as
(
       select 
              te.*,
              ed.EntityID,
              gi.CustomsItemFullClassification,
              gi.LeadDocumentTitle,
              -- Check for single unique classification across the document
              'MinClass' = MIN(gi.CustomsItemFullClassification) OVER(PARTITION BY ed.EntityID),
              'MaxClass' = MAX(gi.CustomsItemFullClassification) OVER(PARTITION BY ed.EntityID),
              -- Number the lines within each document
              'LineNumberPerDoc' = ROW_NUMBER() OVER(PARTITION BY ed.EntityID ORDER BY (SELECT NULL))
       from [Customs_Extended].[DM].[DataMining_TableExtraction] te
       join [Customs_Pilot].[Infrastructure].[Docs_EntityDocument] ed
              on te.DocumentID = ed.DocumentID
       join [CustomsDWH_Pilot].FCT.DealFile_fact_GoodsItem gi
              on ed.EntityID = gi.LeadDocumentID
       where ed.EntityTypeID = 1055
       and te.GeneralProduct is not null
       and exists (select 1
                   from cte
                   where cte.LeadDocumentID = ed.[EntityID])
),
FinalDeduped as 
(
    select *,
           -- Number unique instances of product details
           'UniqueInstanceID' = ROW_NUMBER() OVER(
                            PARTITION BY Description, Brand, Model, GeneralProduct, Purpose 
                            ORDER BY EntityID 
                         )
    from cte2
    where MinClass = MaxClass 
    and LineNumberPerDoc = 1 -- This ensures we only take the first line from each LeadDocumentID to get better diversity in the dataset
)
select *
from FinalDeduped
where UniqueInstanceID = 1