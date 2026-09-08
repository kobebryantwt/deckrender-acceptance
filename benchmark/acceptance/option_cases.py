"""Bounded option coverage; source markers are independent of target rendering."""

def variants():
    # Each image route and interface gets first-page selection and each encoding.
    for engine,formats in [('local',['pptx','pdf']),('cloud',['pptx','pdf','ppt','key','docx'])]:
        for fmt in formats:
            yield fmt,engine,dict(variantId='page-single',variantLabel='单页筛选：仅输出源第 1 页',pages='1',expectedSourcePages=[1],expectedSupport=True)
            for encoding in ['png','jpg','webp']:
                rejected=engine=='local' and encoding=='webp' or fmt=='key' and encoding=='jpg'
                v=dict(variantId='encoding-'+encoding,variantLabel='图片编码 '+encoding+('：明确拒绝' if rejected else '：检查真实解码格式，仅输出源第 1 页'),pages='1',imageFormat=encoding,expectedSourcePages=[1],expectedSupport=not rejected)
                if rejected:v['expectedOptionError']='unsupportedOptionCode'
                yield fmt,engine,v
    for fmt in ['pptx','pdf']:
        for engine in ['local','cloud']:
            for name,spec,pages in [('range','2-3',[2,3]),('sparse','1,3',[1,3]),('deduplicate','3,1,3',[1,3])]:
                yield fmt,engine,dict(variantId='page-'+name,variantLabel='页面筛选 '+repr(spec)+'：源页 '+str(pages)+'，JSON pages 仍为源总页数 3',pages=spec,expectedSourcePages=pages,expectedSupport=True)
            for name,spec in [('zero','0'),('reverse','3-1'),('syntax','abc'),('out-of-range','4'),('blank',' ')]:
                yield fmt,engine,dict(variantId='page-'+name,variantLabel='非法页面筛选 '+repr(spec)+'：usage_error 且无产物',pages=spec,expectedOptionError='invalidPagesCode',expectedSupport=False)
            yield fmt,engine,dict(variantId='page-pdf-rejected',variantLabel='PDF 输出不接受页面筛选：unsupported_option',outputTarget='pdf',pages='1',expectedOptionError='unsupportedOptionCode',expectedSupport=False)
