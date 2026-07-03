You need to use the TAGS below for response.
- <think> your_think_here </think>: This tag is used for analyzing why the above task is prcessed wrong.
- <error_reason> your_error_reason_here </error_reason>: Output the brief error reason of why the above task is processed wrong.
- <error_category> your_error_category_here </error_category>: Categorize the error and output a error category.
- <error_tag> your_error_tag_here </error_tag>: Output the error tag of the category the error belongs to based on the error reason above. If the error category belongs to one of the existing categories, output its error tag, e.g., <error_tag> (1) </error_tag>. If none of the current error category match this error, output the NONE error tag, e.g., <error_tag> NONE </error_tag>